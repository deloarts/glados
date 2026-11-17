"""Read-only schedule board. It re-runs the recompute's walk without
persisting, so it stays correct even if a recompute was missed, and
includes the unassigned bucket planners work from."""

from datetime import date
from datetime import datetime
from datetime import timedelta
from functools import partial

from anyio import to_thread

from src.modules.fulfillment.application.dto.production_schedule_dto import MachineCapacityDayResult
from src.modules.fulfillment.application.dto.production_schedule_dto import (
    ScheduleBoardMachineResult,
)
from src.modules.fulfillment.application.dto.production_schedule_dto import ScheduleBoardOrderResult
from src.modules.fulfillment.application.dto.production_schedule_dto import ScheduleBoardPoolResult
from src.modules.fulfillment.application.dto.production_schedule_dto import ScheduleBoardResult
from src.modules.fulfillment.application.services.scheduling_context import SchedulingRepos
from src.modules.fulfillment.application.use_cases.production_schedule._walk_inputs import (
    ScheduleWalkInputs,
)
from src.modules.fulfillment.application.use_cases.production_schedule._walk_inputs import (
    build_schedule_walk_inputs,
)
from src.modules.fulfillment.domain.entities.admin_settings.production import (
    AdminProductionSettings,
)
from src.modules.fulfillment.domain.entities.machine_pool import MachinePool
from src.modules.fulfillment.domain.entities.production_machine import ProductionMachine
from src.modules.fulfillment.domain.entities.production_order import ProductionOrder
from src.modules.fulfillment.domain.services.scheduling import ScheduledOrder
from src.modules.fulfillment.domain.services.scheduling import ScheduleWalkResult
from src.modules.fulfillment.domain.services.scheduling import compute_daily_capacity
from src.modules.fulfillment.domain.services.scheduling import schedule_all_propagated
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
from src.modules.fulfillment.ports.outbound.schedule_recompute_generation_port import (
    IScheduleRecomputeGenerationCounter,
)
from src.modules.platform.application.services.tenant_timezone import tenant_zone
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork
from src.shared_kernel.domain.services.clock import now_utc


def _to_order_result(scheduled: ScheduledOrder, order: ProductionOrder) -> ScheduleBoardOrderResult:
    return ScheduleBoardOrderResult(
        order_id=order.id,
        production_order_number=order.production_order_number,
        lot_id=order.lot_id,
        lot_number=order.lot_number,
        project_number=order.project_number,
        made_item_id=order.made_item_id,
        made_item_part_number=order.made_item_part_number,
        made_item_revision=order.made_item_revision,
        quantity=order.quantity,
        queue_sequence=order.queue_sequence,
        status=order.status,
        pinned=order.pinned,
        planned_start=scheduled.planned_start,
        planned_end=scheduled.planned_end,
        lot_position_sequence=order.lot_position_sequence,
        lot_position_count=order.lot_position_count,
        conflicts=scheduled.conflicts,
        machine_pool_id=order.machine_pool_id,
        is_floating=order.machine_id is None and order.machine_pool_id is not None,
        trial_machine_id=scheduled.trial_machine_id,
    )


class GetScheduleBoard:
    def __init__(
        self,
        repos: SchedulingRepos,
        machine_repo: IProductionMachineRepository,
        calendar_repo: IMachineCalendarRepository,
        settings_repo: IFulfillmentSettingsRepository,
        pool_repo: IMachinePoolRepository | None = None,
        downtime_repo: IMachineDowntimeRepository | None = None,
        generation_counter: IScheduleRecomputeGenerationCounter | None = None,
        uow: IUnitOfWork | None = None,
    ) -> None:
        self._repos = repos
        self._uow = uow
        self._generation_counter = generation_counter
        self._machines = machine_repo
        self._calendars = calendar_repo
        self._settings = settings_repo
        self._pools = pool_repo
        self._downtimes = downtime_repo

    async def execute(self, date_from: date, date_to: date) -> ScheduleBoardResult:
        dates = [date_from + timedelta(days=i) for i in range((date_to - date_from).days + 1)]
        settings = await self._settings.get_production()
        now = now_utc()

        pools = await self._load_active_pools()
        active_machines = await self._load_active_machines()
        active_machine_ids = [m.id for m in active_machines]

        result, inputs = await self._run_walk(settings, now, pools, active_machine_ids)

        machine_results = self._build_machine_results(active_machines, result, inputs, dates)
        unassigned_results = self._build_unassigned_results(
            result, inputs, {pool.id for pool in pools}
        )
        pool_results = self._build_pool_results(pools, machine_results, result, inputs, dates)

        return ScheduleBoardResult(
            machines=machine_results,
            pools=pool_results,
            unassigned=unassigned_results,
            stale_since=await self._stale_since(),
        )

    async def _stale_since(self) -> datetime | None:
        """Since when the stored dates await a walk; None when the
        coordinator is not wired or not reachable."""
        if self._generation_counter is None:
            return None
        try:
            return await self._generation_counter.stale_since()
        except Exception:
            log.warning("Could not read whether the schedule awaits a walk.", exc_info=True)
            return None

    async def _load_active_pools(self) -> list[MachinePool]:
        """Every active pool; get_multi would clamp to one page."""
        if self._pools is None:
            return []
        pools = await self._pools.get_all()
        return [p for p in pools if not p.archived]

    async def _load_active_machines(self) -> list[ProductionMachine]:
        """Every active machine; get_multi would clamp to one page."""
        machines = await self._machines.get_all()
        return [m for m in machines if not m.archived]

    async def _run_walk(
        self,
        settings: AdminProductionSettings,
        now: datetime,
        pools: list[MachinePool],
        active_machine_ids: list[int],
    ) -> tuple[ScheduleWalkResult, ScheduleWalkInputs]:
        """One unified walk, as in the recompute, never persisted."""
        orders = await self._repos.orders.get_all_non_terminal()
        inputs = await build_schedule_walk_inputs(
            orders,
            self._repos,
            self._machines,
            self._calendars,
            self._pools,
            settings,
            settings.response_time_days,
            pools=pools,
            # Idle machines still get a capacity row.
            extra_machine_ids=active_machine_ids,
            downtime_repo=self._downtimes,
            now=now,
            zone=await tenant_zone(self._settings),
        )
        # The reads are done; ending their transaction keeps the CPU phase
        # from sitting idle in one, which the server ends after a while. The
        # board writes nothing, so it ends the way the request would.
        if self._uow is not None:
            await self._uow.rollback()
        # CPU-heavy, so offloaded from the event loop.
        result, _passes = await to_thread.run_sync(
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
        return result, inputs

    def _build_machine_results(
        self,
        active_machines: list[ProductionMachine],
        result: ScheduleWalkResult,
        inputs: ScheduleWalkInputs,
        dates: list[date],
    ) -> list[ScheduleBoardMachineResult]:
        """Per-machine capacity and orders. Capacity counts floating pool
        orders placed on the machine, but `orders` lists only
        machine-assigned ones, since the pool's machine choice is deferred."""
        orders_by_id = inputs.orders_by_id
        machine_results = []
        for machine in active_machines:
            machine_scheduled = result.by_machine.get(machine.id, [])
            floating_on_machine = [
                s
                for pool_scheduled in result.by_pool.values()
                for s in pool_scheduled
                if s.trial_machine_id == machine.id
            ]
            calendar = inputs.machine_calendars[machine.id]
            capacity = compute_daily_capacity(
                calendar, machine_scheduled + floating_on_machine, dates
            )
            machine_results.append(
                ScheduleBoardMachineResult(
                    machine_id=machine.id,
                    machine_internal_name=machine.internal_name,
                    orders=[
                        _to_order_result(s, orders_by_id[s.order_id])
                        for s in machine_scheduled
                        if s.order_id in orders_by_id
                    ],
                    capacity=[
                        MachineCapacityDayResult(
                            date=d,
                            booked_minutes=booked,
                            available_minutes=available,
                            overbooked_minutes=max(0, booked - available),
                        )
                        for d, (booked, available) in capacity.items()
                    ],
                )
            )
        return machine_results

    def _build_unassigned_results(
        self,
        result: ScheduleWalkResult,
        inputs: ScheduleWalkInputs,
        shown_pool_ids: set[int],
    ) -> list[ScheduleBoardOrderResult]:
        """The unassigned and manual buckets, plus the floating orders of
        pools the board has no row for, pools without members and archived
        ones, whose orders would otherwise be dropped."""
        orders_by_id = inputs.orders_by_id
        unassigned_results = [
            _to_order_result(s, orders_by_id[s.order_id])
            for s in result.unassigned + result.manual
            if s.order_id in orders_by_id
        ]
        for pool_id, pool_scheduled in result.by_pool.items():
            if pool_id in inputs.pool_members and pool_id in shown_pool_ids:
                continue
            unassigned_results = unassigned_results + [
                _to_order_result(s, orders_by_id[s.order_id])
                for s in pool_scheduled
                if s.order_id in orders_by_id
            ]
        return unassigned_results

    def _build_pool_results(
        self,
        pools: list[MachinePool],
        machine_results: list[ScheduleBoardMachineResult],
        result: ScheduleWalkResult,
        inputs: ScheduleWalkInputs,
        dates: list[date],
    ) -> list[ScheduleBoardPoolResult]:
        """A pool's capacity is the per-date sum of its members' capacity."""
        if self._pools is None:
            return []
        orders_by_id = inputs.orders_by_id
        capacity_by_machine_id = {m.machine_id: m.capacity for m in machine_results}
        orders_by_machine_id = {m.machine_id: m.orders for m in machine_results}
        pool_results: list[ScheduleBoardPoolResult] = []
        for pool in pools:
            capacity_by_date: dict[date, list[int]] = {d: [0, 0] for d in dates}
            for member_id in pool.machine_ids:
                for day in capacity_by_machine_id.get(member_id, []):
                    totals = capacity_by_date.setdefault(day.date, [0, 0])
                    totals[0] += day.booked_minutes
                    totals[1] += day.available_minutes
            pool_capacity = [
                MachineCapacityDayResult(
                    date=d,
                    booked_minutes=b,
                    available_minutes=a,
                    overbooked_minutes=max(0, b - a),
                )
                for d, (b, a) in sorted(capacity_by_date.items())
            ]
            pool_orders = [
                order_result
                for member_id in pool.machine_ids
                for order_result in orders_by_machine_id.get(member_id, [])
                if order_result.machine_pool_id == pool.id
            ] + [
                _to_order_result(s, orders_by_id[s.order_id])
                for s in result.by_pool.get(pool.id, [])
                if s.order_id in orders_by_id
            ]
            pool_results.append(
                ScheduleBoardPoolResult(
                    pool_id=pool.id,
                    pool_name=pool.name,
                    machine_ids=pool.machine_ids,
                    orders=pool_orders,
                    capacity=pool_capacity,
                )
            )
        return pool_results
