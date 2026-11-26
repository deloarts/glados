"""Re-walks the whole production schedule with schedule_all_propagated and
persists the planned dates. Every mutation that can move a date calls
execute_all() right after its own commit. Built with `defer`, as the app
wires it, execute_all() only requests the walk: it draws a generation and
stages a ScheduleRecomputeRequested event in a transaction of its own, and
the `schedule` event worker walks on a fresh session (walk_covering), as the
periodic tick does. Auto-Plan walks in the request, because its answer is
the plan.

The walk reads every order long before it writes, so it writes only the
planned window and its author, only for orders whose values it changed, and
skips an order whose pin changed since its read (save_planning_fields).
Every other column, and a window a person pinned in the meantime, keep what
was committed; the walk that this later commit triggers takes them into
account.

Bursts of mutations are coalesced. Each request increments a shared Redis
generation counter, and every walk takes a blocking advisory lock. Under the
lock it skips the walk if the processed generation already covers the
request's; otherwise it samples the current generation before reading any
order and records that as processed afterwards. Because each commit happens
before its increment (a request made while an Idempotency-Key route holds
the commits waits for the commit that ends the hold), the walk covers every
commit that incremented before the lock was taken. A Redis error fails open
to an unconditional walk, which still takes the lock, so Redis never blocks a
mutation and never lets two walks run at once.
"""

import time
from datetime import datetime
from functools import partial

from anyio import to_thread

from src.modules.fulfillment.application.services.scheduling_context import SchedulingRepos
from src.modules.fulfillment.application.services.scheduling_context import (
    describe_external_work_chains,
)
from src.modules.fulfillment.application.services.scheduling_context import prefetch_scheduling_data
from src.modules.fulfillment.application.use_cases.production_schedule._walk_inputs import (
    ScheduleWalkInputs,
)
from src.modules.fulfillment.application.use_cases.production_schedule._walk_inputs import (
    build_schedule_walk_inputs,
)
from src.modules.fulfillment.domain.entities.admin_settings.production import (
    AdminProductionSettings,
)
from src.modules.fulfillment.domain.entities.production_order import ProductionOrder
from src.modules.fulfillment.domain.events.schedule_events import ScheduleRecomputeRequested
from src.modules.fulfillment.domain.services.scheduling import OrderSchedulingContext
from src.modules.fulfillment.domain.services.scheduling import ScheduleWalkResult
from src.modules.fulfillment.domain.services.scheduling import placed_ends_by_position
from src.modules.fulfillment.domain.services.scheduling import schedule_all_propagated
from src.modules.fulfillment.domain.services.scheduling.external_work import forecast_external_work
from src.modules.fulfillment.ports.outbound.fulfillment_settings_repository import (
    IFulfillmentSettingsRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.machine_calendar_repository import (
    IMachineCalendarRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.machine_downtime_repository import (
    IMachineDowntimeRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.machine_pool_repository import (
    IMachinePoolRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.production_machine_repository import (
    IProductionMachineRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.production_order_repository import (
    ProductionOrderPlanningFields,
)
from src.modules.fulfillment.ports.outbound.schedule_recompute_generation_port import (
    IScheduleRecomputeGenerationCounter,
)
from src.modules.fulfillment.ports.outbound.schedule_recompute_lock_port import (
    IScheduleRecomputeLock,
)
from src.modules.platform.application.services.tenant_timezone import tenant_zone
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.ports.outbound.event_bus_port import IEventBus
from src.modules.platform.ports.outbound.unit_of_work_port import IDeferringUnitOfWork
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork
from src.shared_kernel.domain.services.clock import now_utc


def _empty_schedule_walk_result() -> ScheduleWalkResult:
    """A fresh empty result. Not a shared constant, because its dict and
    list fields are mutable."""
    return ScheduleWalkResult(
        by_machine={}, by_pool={}, manual=[], unassigned=[], machine_cursors={}
    )


def _walked_contexts(inputs: ScheduleWalkInputs) -> list[OrderSchedulingContext]:
    """Every order context the walk placed, in whatever queue it sat."""
    contexts: list[OrderSchedulingContext] = []
    for queue in [*inputs.machine_queues.values(), *inputs.pool_queues.values()]:
        contexts.extend(queue)
    contexts.extend(inputs.manual_queue)
    contexts.extend(inputs.unassigned)
    return contexts


def _changed_planning_fields(
    result: ScheduleWalkResult, orders_by_id: dict[int, ProductionOrder]
) -> list[ProductionOrderPlanningFields]:
    """The planned window and author of every walked order whose values
    differ from what the walk read, with the pin flag it read. A pinned
    window is a person's override and keeps its author; everything else is
    attributed to the scheduler."""
    plans: list[ProductionOrderPlanningFields] = []
    for scheduled in result.all_orders():
        order = orders_by_id.get(scheduled.order_id)
        if order is None:
            continue
        planned_by_id = order.planned_by_id if order.pinned else None
        if (
            scheduled.planned_start == order.planned_start
            and scheduled.planned_end == order.planned_end
            and planned_by_id == order.planned_by_id
        ):
            continue
        plans.append(
            ProductionOrderPlanningFields(
                order_id=order.id,
                planned_start=scheduled.planned_start,
                planned_end=scheduled.planned_end,
                planned_by_id=planned_by_id,
                pinned_when_read=order.pinned,
                place_when_read=(order.machine_id, order.machine_pool_id, order.queue_sequence),
            )
        )
    return plans


class RecomputeMachineSchedule:
    def __init__(
        self,
        repos: SchedulingRepos,
        machine_repo: IProductionMachineRepository,
        calendar_repo: IMachineCalendarRepository,
        settings_repo: IFulfillmentSettingsRepository,
        pool_repo: IMachinePoolRepository | None = None,
        downtime_repo: IMachineDowntimeRepository | None = None,
        *,
        uow: IUnitOfWork,
        generation_counter: IScheduleRecomputeGenerationCounter | None = None,
        recompute_lock: IScheduleRecomputeLock | None = None,
        event_bus: IEventBus | None = None,
        defer: bool = False,
    ) -> None:
        """With `defer`, execute_all() requests the walk through `event_bus`
        instead of walking; see the module docstring."""
        if defer and event_bus is None:
            raise ValueError("A deferred schedule recompute needs the event bus.")
        self._repos = repos
        self._machines = machine_repo
        self._calendars = calendar_repo
        self._settings = settings_repo
        self._pools = pool_repo
        self._downtimes = downtime_repo
        self._uow = uow
        self._generation_counter = generation_counter
        self._recompute_lock = recompute_lock
        self._bus = event_bus
        self._defer = defer

    async def execute_all(
        self,
        response_time_days: int | None = None,
        settings: AdminProductionSettings | None = None,
    ) -> ScheduleWalkResult:
        """Coalescing entry point (see the module docstring). Deferred, it
        returns an empty result, since the walk has not run yet. While the
        caller holds the session's commits, the request waits for the commit
        that ends the hold, so its generation is still drawn after the work
        commits."""
        if isinstance(self._uow, IDeferringUnitOfWork) and self._uow.defer_until_committed(
            partial(self._execute_after_hold, response_time_days, settings)
        ):
            return _empty_schedule_walk_result()
        counter = self._generation_counter
        # Marked before the generation is drawn: a walk that covers the
        # generation takes the mark with it, and one that took the mark
        # earlier walks again for this request.
        if self._defer and counter is not None:
            await self._safe_mark_stale(counter)
        generation = await self._safe_increment_generation(counter) if counter is not None else None
        if self._defer:
            assert self._bus is not None
            await self._bus.publish(ScheduleRecomputeRequested(generation=generation))
            await self._uow.commit()
            return _empty_schedule_walk_result()
        return await self.walk_covering(generation, response_time_days, settings)

    async def _execute_after_hold(
        self, response_time_days: int | None, settings: AdminProductionSettings | None
    ) -> None:
        try:
            await self.execute_all(response_time_days, settings)
        except Exception:
            log.exception("Schedule recompute failed after a held commit; the write is committed")

    async def walk_covering(
        self,
        generation: int | None,
        response_time_days: int | None = None,
        settings: AdminProductionSettings | None = None,
    ) -> ScheduleWalkResult:
        """Walks under the recompute lock unless a walk already covered
        `generation`; None walks unconditionally, as the periodic tick and a
        request drawn while the coordinator was down do."""
        counter = self._generation_counter
        lock = self._recompute_lock
        if lock is None:
            return await self._walk_and_persist(response_time_days, settings)

        async with lock.lock():
            processed = (
                await self._safe_processed_generation(counter)
                if counter is not None and generation is not None
                else None
            )
            if generation is not None and processed is not None and processed >= generation:
                log.info(
                    f"Schedule recompute coalesced: generation {generation} already "
                    f"covered by a concurrent walk (processed={processed})."
                )
                # A request that marked the schedule stale while that walk ran
                # but drew a generation it covered leaves a mark no later walk
                # takes; with no newer request pending, the dates are current.
                if counter is not None:
                    latest = await self._safe_current_generation(counter, fallback=generation)
                    if latest <= processed:
                        await self._safe_take_stale(counter)
                return _empty_schedule_walk_result()

            # Cleared before reading orders, so a request committed while the
            # walk runs marks the schedule stale again.
            taken = await self._safe_take_stale(counter) if counter is not None else None
            # Sampled under the lock before reading orders (module docstring).
            current = (
                await self._safe_current_generation(counter, fallback=generation or 0)
                if counter is not None
                else None
            )
            try:
                result = await self._walk_and_persist(response_time_days, settings)
            except Exception:
                # The dates still lag what was committed: the mark goes back,
                # from when it was first set, or from now for a walk that ran
                # without one, as Auto-Plan's does.
                if counter is not None:
                    await self._safe_mark_stale(counter, taken)
                raise
            if counter is not None and current is not None:
                await self._safe_mark_processed(counter, max(current, generation or 0))
            return result

    async def _walk_and_persist(
        self,
        response_time_days: int | None,
        settings: AdminProductionSettings | None,
    ) -> ScheduleWalkResult:
        """Walks every non-terminal order in one unified pass and commits
        once. Callers that already hold the settings pass them in."""
        started = time.perf_counter()
        orders = await self._repos.orders.get_all_non_terminal()
        external_work_lot_ids = await self._repos.lots.get_ids_with_external_work()
        if not orders and not external_work_lot_ids:
            return _empty_schedule_walk_result()

        settings = settings or await self._settings.get_production()
        if response_time_days is None:
            response_time_days = settings.response_time_days
        zone = await tenant_zone(self._settings)
        now = now_utc()
        if not orders:
            # A lot of external work only still needs its forecast.
            prefetch = await prefetch_scheduling_data(
                [],
                self._repos,
                extra_lot_ids=external_work_lot_ids,
                zone=zone,
                today=now.astimezone(zone).date(),
            )
            chains = await describe_external_work_chains(
                external_work_lot_ids,
                prefetch,
                self._repos,
                settings.default_external_lead_days,
                zone=zone,
            )
            await self._repos.lots.save_position_forecasts(
                forecast_external_work(
                    chains, {}, response_time_days, settings.external_safety_margin_days
                )
            )
            await self._uow.commit()
            return _empty_schedule_walk_result()

        inputs = await build_schedule_walk_inputs(
            orders,
            self._repos,
            self._machines,
            self._calendars,
            self._pools,
            settings,
            response_time_days,
            downtime_repo=self._downtimes,
            now=now,
            extra_lot_ids=external_work_lot_ids,
            zone=zone,
        )
        # Read with the orders, so the walk's read transaction holds both.
        external_work_chains = await describe_external_work_chains(
            external_work_lot_ids,
            inputs.prefetch,
            self._repos,
            settings.default_external_lead_days,
            zone=zone,
        )
        # The reads are done; ending their transaction keeps the CPU phase
        # from sitting idle in one, which the server ends after a while. The
        # write guards each row against a change made meanwhile.
        await self._uow.commit()
        # The walk is pure and CPU-heavy, so it runs in a worker thread to
        # keep the event loop responsive. Only plain entities go in.
        result, passes = await to_thread.run_sync(
            partial(
                schedule_all_propagated,
                inputs.machine_queues,
                inputs.machine_calendars,
                inputs.pool_queues,
                inputs.pool_members,
                inputs.manual_queue,
                inputs.manual_calendar,
                inputs.unassigned,
                now,
            )
        )
        if result.unsettled_order_ids:
            log.warning(
                "Schedule recompute stopped at the propagation pass limit with "
                f"production orders {sorted(result.unsettled_order_ids)} still moving; "
                "they wait on a cycle, such as a step queued ahead of its own "
                "predecessor on one machine. Their dates are from the last pass."
            )

        # One lean write for every changed order: nothing here reads the
        # saved rows back, so the per-row save-and-reload is skipped.
        await self._repos.orders.save_planning_fields(
            _changed_planning_fields(result, inputs.orders_by_id)
        )

        # The walk forecasts the positions that feed a later order; the
        # lots' own chains add every other external position, such as the
        # last one of a lot. Both read the same chain, so they agree.
        forecasts = dict(result.external_forecasts)
        placed_end_by_position = placed_ends_by_position(_walked_contexts(inputs), result)
        for forecast in forecast_external_work(
            external_work_chains,
            placed_end_by_position,
            response_time_days,
            settings.external_safety_margin_days,
        ):
            forecasts[forecast.position_id] = forecast
        await self._repos.lots.save_position_forecasts(list(forecasts.values()))

        await self._uow.commit()

        elapsed_ms = (time.perf_counter() - started) * 1000
        log.info(
            f"Global schedule recompute: {len(orders)} order(s), "
            f"{len(result.by_machine)} machine(s), {len(result.by_pool)} pool(s), "
            f"{passes} pass(es) in {elapsed_ms:.1f}ms."
        )
        return result

    @staticmethod
    async def _safe_increment_generation(
        counter: IScheduleRecomputeGenerationCounter,
    ) -> int | None:
        try:
            return await counter.increment_generation()
        except Exception:
            log.warning(
                "Schedule-recompute coordinator unavailable; running the walk unconditionally.",
                exc_info=True,
            )
            return None

    @staticmethod
    async def _safe_processed_generation(
        counter: IScheduleRecomputeGenerationCounter,
    ) -> int | None:
        try:
            return await counter.processed_generation()
        except Exception:
            log.warning(
                "Schedule-recompute coordinator unavailable reading the processed "
                "generation; proceeding with the walk rather than risk wrongly "
                "skipping it.",
                exc_info=True,
            )
            return None

    @staticmethod
    async def _safe_current_generation(
        counter: IScheduleRecomputeGenerationCounter, *, fallback: int
    ) -> int:
        try:
            return await counter.current_generation()
        except Exception:
            log.warning(
                "Schedule-recompute coordinator unavailable sampling the current "
                "generation; recording only this walk's own generation as processed.",
                exc_info=True,
            )
            return fallback

    @staticmethod
    async def _safe_mark_stale(
        counter: IScheduleRecomputeGenerationCounter, at: datetime | None = None
    ) -> None:
        try:
            await counter.mark_stale(at or now_utc())
        except Exception:
            log.warning("Could not record that the schedule awaits a walk.", exc_info=True)

    @staticmethod
    async def _safe_take_stale(counter: IScheduleRecomputeGenerationCounter) -> datetime | None:
        try:
            return await counter.take_stale_since()
        except Exception:
            log.warning("Could not clear the schedule's stale mark.", exc_info=True)
            return None

    @staticmethod
    async def _safe_mark_processed(
        counter: IScheduleRecomputeGenerationCounter, generation: int
    ) -> None:
        try:
            await counter.mark_processed(generation)
        except Exception:
            log.warning(
                "Could not record the completed schedule-recompute generation; a "
                "future mutation may trigger one redundant walk.",
                exc_info=True,
            )
