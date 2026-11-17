"""Groups a batch of production orders into the queues and calendars of one
unified schedule_all walk, shared by the recompute and the schedule board
so both build identical inputs."""

from collections.abc import Iterable
from dataclasses import dataclass
from dataclasses import replace
from datetime import date
from datetime import datetime
from datetime import timedelta
from datetime import tzinfo

from src.modules.fulfillment.application.services.scheduling_context import SchedulingPrefetch
from src.modules.fulfillment.application.services.scheduling_context import SchedulingRepos
from src.modules.fulfillment.application.services.scheduling_context import build_contexts
from src.modules.fulfillment.application.services.scheduling_context import build_machine_calendars
from src.modules.fulfillment.application.services.scheduling_context import holiday_dates
from src.modules.fulfillment.application.services.scheduling_context import prefetch_scheduling_data
from src.modules.fulfillment.domain.entities.admin_settings.production import (
    AdminProductionSettings,
)
from src.modules.fulfillment.domain.entities.machine_pool import MachinePool
from src.modules.fulfillment.domain.entities.production_order import ProductionOrder
from src.modules.fulfillment.domain.services.scheduling import MachineCalendar
from src.modules.fulfillment.domain.services.scheduling import OrderSchedulingContext
from src.modules.fulfillment.domain.services.scheduling import build_machine_calendar
from src.modules.fulfillment.domain.value_objects.production_status import ProductionOrderStatus
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
from src.shared_kernel.domain.services.clock import as_utc
from src.shared_kernel.domain.services.clock import now_utc


@dataclass(frozen=True)
class ScheduleWalkInputs:
    """Inputs for one global walk, plus `orders_by_id` for writing results
    back onto the entities."""

    machine_queues: dict[int, list[OrderSchedulingContext]]
    machine_calendars: dict[int, MachineCalendar]
    pool_queues: dict[int, list[OrderSchedulingContext]]
    pool_members: dict[int, list[int]]
    manual_queue: list[OrderSchedulingContext]
    manual_calendar: MachineCalendar
    unassigned: list[OrderSchedulingContext]
    orders_by_id: dict[int, ProductionOrder]


def _freeze(
    contexts: list[OrderSchedulingContext], now: datetime, until: datetime
) -> list[OrderSchedulingContext]:
    """The contexts with every queued order whose planned start lies between
    now and `until` frozen, so the walk keeps its window."""
    return [
        replace(ctx, frozen=True)
        if ctx.status == ProductionOrderStatus.QUEUED
        and not ctx.pinned
        and ctx.existing_planned_start is not None
        and ctx.existing_planned_end is not None
        and now <= as_utc(ctx.existing_planned_start) <= until
        else ctx
        for ctx in contexts
    ]


async def build_schedule_walk_inputs(
    orders: list[ProductionOrder],
    repos: SchedulingRepos,
    machine_repo: IProductionMachineRepository,
    calendar_repo: IMachineCalendarRepository,
    pool_repo: IMachinePoolRepository | None,
    settings: AdminProductionSettings,
    response_time_days: int,
    pools: list[MachinePool] | None = None,
    extra_machine_ids: Iterable[int] = (),
    downtime_repo: IMachineDowntimeRepository | None = None,
    now: datetime | None = None,
    *,
    zone: tzinfo,
) -> ScheduleWalkInputs:
    """Builds the inputs for one global walk over `orders`.

    `pools` is an optional pre-fetched roster. `extra_machine_ids` gives
    idle machines a calendar so the board can show their capacity. A pool
    without members is left out of `pool_members`, so its queue degrades to
    unassigned. With downtime_repo, down machines lose capacity and their
    orders are flagged. `zone` is the tenant's timezone: calendar hours are
    local to it and every day of the contexts is a day of it."""
    orders_by_id = {o.id: o for o in orders}
    machine_orders, machineless_orders = _group_orders_by_machine(orders)
    down_machine_ids = await _resolve_down_machine_ids(downtime_repo, machine_orders, now)
    prefetch = await prefetch_scheduling_data(orders, repos, pool_repo, zone=zone)

    machine_queues = await _build_machine_queues(
        machine_orders,
        repos,
        machine_repo,
        response_time_days,
        settings,
        down_machine_ids,
        prefetch,
        zone,
    )
    manual_queue, pool_queues, unassigned = await _split_machineless_contexts(
        machineless_orders, repos, pool_repo, response_time_days, settings, prefetch, zone
    )
    pool_members = _resolve_pool_members(pool_queues, pools, prefetch)
    frozen_until = (
        now + timedelta(hours=settings.frozen_window_hours)
        if now is not None and settings.frozen_window_hours > 0
        else None
    )
    if frozen_until is not None:
        assert now is not None
        machine_queues = {
            mid: _freeze(queue, now, frozen_until) for mid, queue in machine_queues.items()
        }
        pool_queues = {pid: _freeze(queue, now, frozen_until) for pid, queue in pool_queues.items()}
        manual_queue = _freeze(manual_queue, now, frozen_until)
        unassigned = _freeze(unassigned, now, frozen_until)

    holidays = await holiday_dates(calendar_repo)
    machine_calendars = await _build_walk_calendars(
        machine_queues,
        pool_members,
        extra_machine_ids,
        calendar_repo,
        settings,
        downtime_repo,
        now,
        zone,
        holidays,
    )
    manual_calendar = build_machine_calendar(
        settings.default_weekly_hours, None, {}, zone=zone, holidays=holidays
    )

    return ScheduleWalkInputs(
        machine_queues=machine_queues,
        machine_calendars=machine_calendars,
        pool_queues=pool_queues,
        pool_members=pool_members,
        manual_queue=manual_queue,
        manual_calendar=manual_calendar,
        unassigned=unassigned,
        orders_by_id=orders_by_id,
    )


async def _build_walk_calendars(
    machine_queues: dict[int, list[OrderSchedulingContext]],
    pool_members: dict[int, list[int]],
    extra_machine_ids: Iterable[int],
    calendar_repo: IMachineCalendarRepository,
    settings: AdminProductionSettings,
    downtime_repo: IMachineDowntimeRepository | None,
    now: datetime | None,
    zone: tzinfo,
    holidays: frozenset[date],
) -> dict[int, MachineCalendar]:
    """Calendars for every machine with orders, every pool member and every
    extra machine id, which is exactly the set schedule_all needs."""
    member_ids = {member_id for ids in pool_members.values() for member_id in ids}
    calendar_machine_ids = sorted(set(machine_queues) | member_ids | set(extra_machine_ids))
    return await build_machine_calendars(
        calendar_machine_ids,
        calendar_repo,
        settings.default_weekly_hours,
        downtime_repo=downtime_repo,
        now=now,
        zone=zone,
        holidays=holidays,
    )


def _group_orders_by_machine(
    orders: list[ProductionOrder],
) -> tuple[dict[int, list[ProductionOrder]], list[ProductionOrder]]:
    """Splits `orders` into per-machine groups (machine_id set) and the
    machine-less remainder (pinned, pool and plain unassigned alike)."""
    machine_orders: dict[int, list[ProductionOrder]] = {}
    machineless_orders: list[ProductionOrder] = []
    for order in orders:
        if order.machine_id is not None:
            machine_orders.setdefault(order.machine_id, []).append(order)
        else:
            machineless_orders.append(order)
    return machine_orders, machineless_orders


async def _resolve_down_machine_ids(
    downtime_repo: IMachineDowntimeRepository | None,
    machine_orders: dict[int, list[ProductionOrder]],
    now: datetime | None,
) -> set[int]:
    """Open downtimes that have begun, of the machines orders are assigned to."""
    if downtime_repo is None or not machine_orders:
        return set()
    open_downtimes = await downtime_repo.get_open_by_machine_ids(
        list(machine_orders.keys()), started_by=now or now_utc()
    )
    return set(open_downtimes.keys())


async def _build_machine_queues(
    machine_orders: dict[int, list[ProductionOrder]],
    repos: SchedulingRepos,
    machine_repo: IProductionMachineRepository,
    response_time_days: int,
    settings: AdminProductionSettings,
    down_machine_ids: set[int],
    prefetch: SchedulingPrefetch,
    zone: tzinfo,
) -> dict[int, list[OrderSchedulingContext]]:
    """One context batch per machine, built against that machine for the
    capability check."""
    if not machine_orders:
        return {}
    machines_by_id = {m.id: m for m in await machine_repo.get_by_ids(list(machine_orders))}
    machine_queues: dict[int, list[OrderSchedulingContext]] = {}
    for machine_id, group in machine_orders.items():
        machine_queues[machine_id] = await build_contexts(
            group,
            repos,
            machine=machines_by_id.get(machine_id),
            response_time_days=response_time_days,
            default_external_lead_days=settings.default_external_lead_days,
            down_machine_ids=down_machine_ids,
            prefetch=prefetch,
            zone=zone,
        )
    return machine_queues


async def _split_machineless_contexts(
    machineless_orders: list[ProductionOrder],
    repos: SchedulingRepos,
    pool_repo: IMachinePoolRepository | None,
    response_time_days: int,
    settings: AdminProductionSettings,
    prefetch: SchedulingPrefetch,
    zone: tzinfo,
) -> tuple[
    list[OrderSchedulingContext],
    dict[int, list[OrderSchedulingContext]],
    list[OrderSchedulingContext],
]:
    """Builds machine-less orders in one batch and splits them into manual,
    pool-floating and unassigned."""
    machineless_contexts = await build_contexts(
        machineless_orders,
        repos,
        machine=None,
        response_time_days=response_time_days,
        pool_repo=pool_repo,
        default_external_lead_days=settings.default_external_lead_days,
        prefetch=prefetch,
        zone=zone,
    )
    manual_queue = [c for c in machineless_contexts if c.is_manual_step]

    pool_queues: dict[int, list[OrderSchedulingContext]] = {}
    unassigned: list[OrderSchedulingContext] = []
    for ctx in machineless_contexts:
        if ctx.is_manual_step:
            continue
        if ctx.machine_pool_id is not None:
            pool_queues.setdefault(ctx.machine_pool_id, []).append(ctx)
        else:
            unassigned.append(ctx)

    return manual_queue, pool_queues, unassigned


def _resolve_pool_members(
    pool_queues: dict[int, list[OrderSchedulingContext]],
    pools: list[MachinePool] | None,
    prefetch: SchedulingPrefetch,
) -> dict[int, list[int]]:
    """Members of every floating pool, from the roster or the prefetch.
    Unresolved and empty pools are left out."""
    pools_by_id: dict[int, MachinePool] = {p.id: p for p in (pools or [])}
    pool_members: dict[int, list[int]] = {}
    for pool_id in pool_queues:
        pool = pools_by_id.get(pool_id) or prefetch.pools_by_id.get(pool_id)
        if pool is not None and pool.machine_ids:
            pool_members[pool_id] = pool.machine_ids
    return pool_members
