"""Data gathering for scheduling: fetches and flattens what the pure
scheduling service needs into OrderSchedulingContext. Lookups are prefetched
per batch so building a context never issues per-order queries.

The scheduler use cases, the lot, production order and QA task reads, the
production KPIs and lifecycle_actions.py all build their contexts, target
dates and conflicts here, so every one of them sees the same schedule.
Every calendar day here is a day of the tenant's default timezone
(`tenant_zone`): a delivery or a planned end counts on the day it falls on
there. The walk callers pass that zone in, and the read paths resolve it
from `SchedulingRepos.settings`.
"""

from collections.abc import Iterable
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC
from datetime import date
from datetime import datetime
from datetime import timedelta
from datetime import tzinfo
from typing import Literal

from src.modules.catalogue.domain.errors import MachineCapabilityMismatchError
from src.modules.fulfillment.domain.entities.lot_position import LotPosition
from src.modules.fulfillment.domain.entities.lot_step import LotStep
from src.modules.fulfillment.domain.entities.machine_calendar_exception import (
    MachineCalendarException,
)
from src.modules.fulfillment.domain.entities.machine_downtime import MachineDowntime
from src.modules.fulfillment.domain.entities.machine_pool import MachinePool
from src.modules.fulfillment.domain.entities.made_item_allocation import MadeItemDemandAllocation
from src.modules.fulfillment.domain.entities.order_item import OrderItem
from src.modules.fulfillment.domain.entities.production_lot import ProductionLot
from src.modules.fulfillment.domain.entities.production_machine import ProductionMachine
from src.modules.fulfillment.domain.entities.production_order import ProductionOrder
from src.modules.fulfillment.domain.services import production_order_rules
from src.modules.fulfillment.domain.services.lifecycle.intents import PRODUCTION_ORDER_INTENTS
from src.modules.fulfillment.domain.services.lifecycle.intents import ProductionOrderContext
from src.modules.fulfillment.domain.services.lot_rules import open_input
from src.modules.fulfillment.domain.services.production_order_rules import assert_capability_match
from src.modules.fulfillment.domain.services.production_order_rules import (
    assert_pool_capability_match,
)
from src.modules.fulfillment.domain.services.production_order_rules import is_position_fully_queued
from src.modules.fulfillment.domain.services.production_order_rules import position_is_manual
from src.modules.fulfillment.domain.services.production_time_rules import last_resumed_at
from src.modules.fulfillment.domain.services.scheduling import DayHours
from src.modules.fulfillment.domain.services.scheduling import EarliestStartExplanation
from src.modules.fulfillment.domain.services.scheduling import MachineCalendar
from src.modules.fulfillment.domain.services.scheduling import OrderSchedulingContext
from src.modules.fulfillment.domain.services.scheduling import PredecessorPosition
from src.modules.fulfillment.domain.services.scheduling import apply_downtimes
from src.modules.fulfillment.domain.services.scheduling import build_machine_calendar
from src.modules.fulfillment.domain.services.scheduling import compute_order_conflicts
from src.modules.fulfillment.domain.services.scheduling import explain_earliest_start
from src.modules.fulfillment.domain.services.scheduling import latest_ready_moment
from src.modules.fulfillment.domain.services.scheduling import position_wait_after_minutes
from src.modules.fulfillment.domain.services.scheduling import predecessor_ready_moment
from src.modules.fulfillment.domain.services.scheduling import ready_after_wait
from src.modules.fulfillment.domain.services.scheduling import resolve_external_predecessor_ready_at
from src.modules.fulfillment.domain.services.scheduling import resolve_input_material_ready_at
from src.modules.fulfillment.domain.services.scheduling import resolve_position_lead_days
from src.modules.fulfillment.domain.services.scheduling import stale_external_predecessor
from src.modules.fulfillment.domain.services.scheduling import step_waits
from src.modules.fulfillment.domain.services.scheduling import stored_predecessor_readiness
from src.modules.fulfillment.domain.services.scheduling.external_work import ExternalWorkChain
from src.modules.fulfillment.domain.services.scheduling.external_work import (
    is_outsourced_unassigned,
)
from src.modules.fulfillment.domain.services.scheduling.external_work import (
    position_has_external_work,
)
from src.modules.fulfillment.domain.services.scheduling.external_work_explanation import (
    remaining_minutes,
)
from src.modules.fulfillment.domain.value_objects.lot_status import TERMINAL_LOT_STATUSES
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionKind
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionStatus
from src.modules.fulfillment.domain.value_objects.lot_status import LotStatus
from src.modules.fulfillment.domain.value_objects.production_status import (
    ACTIVE_PRODUCTION_ORDER_STATUSES,
)
from src.modules.fulfillment.domain.value_objects.production_status import ProductionOrderStatus
from src.modules.fulfillment.domain.value_objects.schedule_conflict import ScheduleConflictReason
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
from src.modules.fulfillment.ports.outbound.repositories.made_item_demand_repository import (
    IMadeItemAllocationRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.made_item_demand_repository import (
    IMadeItemDemandItemRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.order_repository import (
    IOrderItemRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.production_lot_repository import (
    IProductionLotRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.production_machine_repository import (
    IProductionMachineRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.production_order_repository import (
    IProductionOrderRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.source_item_demand_repository import (
    ISourceItemAllocationRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.source_item_demand_repository import (
    ISourceItemDemandRepository,
)
from src.modules.platform.application.services.tenant_timezone import tenant_zone
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.services.quantities import quantity_gt
from src.modules.platform.infrastructure.logging.logger import log
from src.shared_kernel.domain.services.clock import as_utc
from src.shared_kernel.domain.services.clock import now_utc
from src.shared_kernel.domain.services.clock import today_in
from src.shared_kernel.domain.value_objects.lifecycle_action import LifecycleAction


@dataclass
class SchedulingRepos:
    orders: IProductionOrderRepository
    lots: IProductionLotRepository
    order_items: IOrderItemRepository
    source_item_demands: ISourceItemDemandRepository
    source_item_allocations: ISourceItemAllocationRepository
    made_item_allocations: IMadeItemAllocationRepository
    made_item_demands: IMadeItemDemandItemRepository
    # Gives the tenant's timezone, the one every scheduling day is read in.
    settings: IFulfillmentSettingsRepository


async def resolve_lot_target_date(lot: ProductionLot, repos: SchedulingRepos) -> date | None:
    """The lot's due date: its explicit required_delivery_date, otherwise the
    earliest desired delivery date of the demands it is allocated to."""
    if lot.required_delivery_date is not None:
        return lot.required_delivery_date
    allocations = await repos.made_item_allocations.get_by_lot_id(lot.id)
    if not allocations:
        return None
    demand_ids = [a.demand_item_id for a in allocations]
    demands = await repos.made_item_demands.get_by_ids(demand_ids)
    dates = [d.desired_delivery_date for d in demands if d.desired_delivery_date is not None]
    return min(dates) if dates else None


TargetDateSource = Literal["lot", "demand"]


async def describe_lot_target_dates(
    lots: list[ProductionLot], repos: SchedulingRepos
) -> dict[int, tuple[date | None, TargetDateSource | None, int | None]]:
    """resolve_lot_target_date for a page of lots in at most two queries,
    with the source ("lot" or "demand") and, for a demand, its id (ties go
    to the lowest id)."""
    result, demand_lots = _split_lots_by_target_date_source(lots)
    if not demand_lots:
        return result
    result.update(await _resolve_demand_target_dates(demand_lots, repos))
    return result


def _split_lots_by_target_date_source(
    lots: list[ProductionLot],
) -> tuple[dict[int, tuple[date | None, TargetDateSource | None, int | None]], list[ProductionLot]]:
    """Splits lots into those with a manual target date and the rest."""
    result: dict[int, tuple[date | None, TargetDateSource | None, int | None]] = {}
    demand_lots: list[ProductionLot] = []
    for lot in lots:
        if lot.required_delivery_date is not None:
            result[lot.id] = (lot.required_delivery_date, "lot", None)
        else:
            demand_lots.append(lot)
    return result, demand_lots


async def _resolve_demand_target_dates(
    demand_lots: list[ProductionLot], repos: SchedulingRepos
) -> dict[int, tuple[date | None, TargetDateSource | None, int | None]]:
    """The demand-derived target date for every lot without a manual one."""
    allocations_by_lot_id: dict[int, list[MadeItemDemandAllocation]] = {
        lot.id: [] for lot in demand_lots
    }
    for allocation in await repos.made_item_allocations.get_by_lot_ids(list(allocations_by_lot_id)):
        if allocation.lot_id is not None and allocation.lot_id in allocations_by_lot_id:
            allocations_by_lot_id[allocation.lot_id].append(allocation)
    demand_ids = {
        allocation.demand_item_id
        for allocations in allocations_by_lot_id.values()
        for allocation in allocations
    }
    demands_by_id = {d.id: d for d in await repos.made_item_demands.get_by_ids(list(demand_ids))}
    result: dict[int, tuple[date | None, TargetDateSource | None, int | None]] = {}
    for lot in demand_lots:
        candidates = [
            (demand.desired_delivery_date, demand.id)
            for allocation in allocations_by_lot_id[lot.id]
            if (demand := demands_by_id.get(allocation.demand_item_id)) is not None
            and demand.desired_delivery_date is not None
        ]
        if candidates:
            earliest_date, demand_item_id = min(candidates)
            result[lot.id] = (earliest_date, "demand", demand_item_id)
        else:
            result[lot.id] = (None, None, None)
    return result


async def _live_order_line(
    position_id: int,
    repos: SchedulingRepos,
    order_items_by_position: dict[int, OrderItem] | None = None,
) -> OrderItem | None:
    """The position's live order line, from the prefetch when given. A
    canceled line beside it supplies nothing."""
    order_item = (
        order_items_by_position.get(position_id)
        if order_items_by_position is not None
        else await repos.order_items.get_by_lot_position_id(position_id)
    )
    return order_item if order_item is not None and order_item.canceled_at is None else None


async def _external_ready_at(
    position_id: int,
    repos: SchedulingRepos,
    order_items_by_position: dict[int, OrderItem] | None = None,
    *,
    zone: tzinfo,
    today: date,
) -> date | None:
    order_item = await _live_order_line(position_id, repos, order_items_by_position)
    if not order_item:
        return None
    return resolve_external_predecessor_ready_at(
        order_item.delivery_date,
        order_item.ready_for_pickup_date,
        order_item.expected_delivery_date,
        zone=zone,
        today=today,
    )


async def _typed_external_date(
    position_id: int,
    repos: SchedulingRepos,
    order_items_by_position: dict[int, OrderItem] | None = None,
) -> date | None:
    """The order item's typed promise (expected delivery, else expected
    pickup). None once a delivery or pickup event happened, since facts are
    never flagged as stale."""
    order_item = await _live_order_line(position_id, repos, order_items_by_position)
    if not order_item:
        return None
    if order_item.delivery_date is not None or order_item.ready_for_pickup_date is not None:
        return None
    return order_item.expected_delivery_date or order_item.expected_pickup_date


async def _internal_ready_moment(
    position_id: int,
    repos: SchedulingRepos,
    sibling_orders_by_position: dict[int, list[ProductionOrder]] | None = None,
) -> datetime | None:
    """The latest persisted planned end over the position's orders, as a
    moment."""
    sibling_orders = (
        sibling_orders_by_position.get(position_id, [])
        if sibling_orders_by_position is not None
        else await repos.orders.get_by_lot_position_id(position_id)
    )
    ends = [as_utc(o.planned_end) for o in sibling_orders if o.planned_end is not None]
    return max(ends) if ends else None


_TERMINAL_POSITION_STATUSES = {
    LotPositionStatus.COMPLETED,
    LotPositionStatus.CANCELED,
}


async def resolve_predecessor_ready_at(
    position: LotPosition,
    lot: ProductionLot,
    repos: SchedulingRepos,
    sibling_orders_by_position: dict[int, list[ProductionOrder]] | None = None,
    order_items_by_position: dict[int, OrderItem] | None = None,
    *,
    zone: tzinfo,
    today: date | None = None,
    response_time_days: int = 0,
) -> tuple[date | None, bool]:
    """Readiness over every earlier position of the lot, so an undated
    position in the middle of the chain cannot be seen through. `today` is
    the day of `zone` a passed expected delivery counts as, the current one
    unless the caller walks against its own clock. `response_time_days` is
    added to every external arrival, not to an in-house end
    (scheduling.buffered_ready_day).

    Returns the latest day in `zone` contributed by open earlier positions,
    each in-house share with the wait after it, and whether any open earlier
    position had no date signal at all. Canceled positions contribute
    nothing, and so do completed ones once their wait is over; neither ever
    makes the chain unknown. It reads the snapshot describe_predecessor_
    positions builds, the one the walk refreshes, so both agree. The
    optional prefetched maps avoid per-position queries."""
    predecessors = await describe_predecessor_positions(
        position,
        lot,
        repos,
        sibling_orders_by_position,
        order_items_by_position,
        zone=zone,
        today=today,
    )
    return stored_predecessor_readiness(predecessors, response_time_days)


async def _predecessor_supplier_lead_days(
    position_id: int,
    repos: SchedulingRepos,
    order_items_by_position: dict[int, OrderItem] | None = None,
) -> int | None:
    order_item = await _live_order_line(position_id, repos, order_items_by_position)
    return order_item.supplier_external_lead_time_days if order_item else None


async def describe_predecessor_positions(
    position: LotPosition,
    lot: ProductionLot,
    repos: SchedulingRepos,
    sibling_orders_by_position: dict[int, list[ProductionOrder]] | None = None,
    order_items_by_position: dict[int, OrderItem] | None = None,
    default_external_lead_days: int = 0,
    material_ready_at_cache: dict[int, date | None] | None = None,
    *,
    zone: tzinfo,
    today: date | None = None,
) -> tuple[PredecessorPosition, ...]:
    """Every earlier open position of the lot as a PredecessorPosition, so
    the propagated walk can redo the chain resolution with in-run dates.
    Its days are days of `zone`, and `today` is as in
    resolve_predecessor_ready_at."""
    return await _describe_open_positions(
        [p for p in lot.positions if p.sequence < position.sequence],
        lot,
        repos,
        sibling_orders_by_position,
        order_items_by_position,
        default_external_lead_days,
        material_ready_at_cache,
        zone=zone,
        today=today if today is not None else today_in(zone),
    )


async def describe_lot_chain(
    lot: ProductionLot,
    repos: SchedulingRepos,
    sibling_orders_by_position: dict[int, list[ProductionOrder]] | None = None,
    order_items_by_position: dict[int, OrderItem] | None = None,
    default_external_lead_days: int = 0,
    material_ready_at_cache: dict[int, date | None] | None = None,
    *,
    zone: tzinfo,
    today: date | None = None,
) -> tuple[PredecessorPosition, ...]:
    """Every open position of the lot, the last one included, described as
    describe_predecessor_positions describes the earlier ones."""
    return await _describe_open_positions(
        list(lot.positions),
        lot,
        repos,
        sibling_orders_by_position,
        order_items_by_position,
        default_external_lead_days,
        material_ready_at_cache,
        zone=zone,
        today=today if today is not None else today_in(zone),
    )


async def _describe_open_positions(
    positions: list[LotPosition],
    lot: ProductionLot,
    repos: SchedulingRepos,
    sibling_orders_by_position: dict[int, list[ProductionOrder]] | None,
    order_items_by_position: dict[int, OrderItem] | None,
    default_external_lead_days: int,
    material_ready_at_cache: dict[int, date | None] | None,
    *,
    zone: tzinfo,
    today: date,
) -> tuple[PredecessorPosition, ...]:
    """The open ones of `positions` as PredecessorPositions, in days of
    `zone`, a passed expected arrival counted as `today`, plus each
    completed one whose wait after it still runs. An in-house share is ready
    at its end plus the position's wait, and the completed orders of a
    position hold it until their wait is over too. An outsourced UNASSIGNED
    position carries the lead days of its steps, since it has no order line
    yet."""
    described: list[PredecessorPosition] = []
    for earlier in positions:
        wait = position_wait_after_minutes(earlier.kind, step_waits(earlier.steps))
        completed_ready_moment = await _completed_ready_moment(
            earlier.id, repos, sibling_orders_by_position, wait, zone=zone, today=today
        )
        closed = earlier.status in _TERMINAL_POSITION_STATUSES
        if closed and (
            earlier.status != LotPositionStatus.COMPLETED or completed_ready_moment is None
        ):
            continue
        external_ready_at = None
        stored_internal_ready_at = None
        typed_external_date = None
        lead_days = None
        order_item_id = None
        arrival_late = False
        outsourced_unassigned = is_outsourced_unassigned(earlier)
        if earlier.kind in (LotPositionKind.EXTERNAL, LotPositionKind.MIXED):
            order_item_id, arrival_late = _arrival_facts(
                await _live_order_line(earlier.id, repos, order_items_by_position), today
            )
            external_ready_at = await _external_ready_at(
                earlier.id, repos, order_items_by_position, zone=zone, today=today
            )
            typed_external_date = await _typed_external_date(
                earlier.id, repos, order_items_by_position
            )
            supplier_override = await _predecessor_supplier_lead_days(
                earlier.id, repos, order_items_by_position
            )
            lead_days = resolve_position_lead_days(
                earlier.steps, supplier_override, default_external_lead_days
            )
        elif outsourced_unassigned:
            lead_days = resolve_position_lead_days(earlier.steps, None, default_external_lead_days)
        stored_internal_ready_moment = None
        if earlier.kind in (LotPositionKind.INTERNAL, LotPositionKind.MIXED) and not closed:
            end = await _internal_ready_moment(earlier.id, repos, sibling_orders_by_position)
            stored_internal_ready_moment = ready_after_wait(end, wait) if end is not None else None
            stored_internal_ready_at = (
                stored_internal_ready_moment.astimezone(zone).date()
                if stored_internal_ready_moment is not None
                else None
            )
        material_ready_at = None
        if earlier.sequence == 1:
            material_ready_at = await resolve_material_ready_at(
                lot, repos, material_ready_at_cache, zone=zone, today=today
            )
        described.append(
            PredecessorPosition(
                position_id=earlier.id,
                sequence=earlier.sequence,
                kind=earlier.kind,
                external_ready_at=external_ready_at,
                stored_internal_ready_at=stored_internal_ready_at,
                lead_days=lead_days,
                typed_external_date=typed_external_date,
                material_ready_at=material_ready_at,
                stored_internal_ready_moment=stored_internal_ready_moment,
                outsourced_unassigned=outsourced_unassigned,
                wait_after_minutes=wait,
                completed_ready_at=(
                    completed_ready_moment.astimezone(zone).date()
                    if completed_ready_moment is not None
                    else None
                ),
                completed_ready_moment=completed_ready_moment,
                completed=closed,
                order_item_id=order_item_id,
                arrival_late=arrival_late,
            )
        )
    return tuple(described)


def _arrival_facts(line: OrderItem | None, today: date) -> tuple[int | None, bool]:
    """The live order line of an external share and whether its expected
    arrival has passed without the delivery or a ready-for-pickup event."""
    if line is None:
        return None, False
    late = (
        line.delivery_date is None
        and line.ready_for_pickup_date is None
        and line.expected_delivery_date is not None
        and line.expected_delivery_date < today
    )
    return line.id, late


async def _completed_ready_moment(
    position_id: int,
    repos: SchedulingRepos,
    sibling_orders_by_position: dict[int, list[ProductionOrder]] | None,
    wait_after_minutes: int,
    *,
    zone: tzinfo,
    today: date,
) -> datetime | None:
    """When the pieces of the position's completed orders are ready, the
    latest actual end plus the wait after the position, while that day is
    `today` or later. None without a wait, since a completed order without
    one holds nothing back, and None once the wait is over."""
    if wait_after_minutes <= 0:
        return None
    sibling_orders = (
        sibling_orders_by_position.get(position_id, [])
        if sibling_orders_by_position is not None
        else await repos.orders.get_by_lot_position_id(position_id)
    )
    moment = latest_ready_moment(
        (o.actual_end, wait_after_minutes)
        for o in sibling_orders
        if o.status == ProductionOrderStatus.COMPLETED
    )
    if moment is None or as_utc(moment).astimezone(zone).date() < today:
        return None
    return moment


async def describe_external_work_chains(
    lot_ids: list[int],
    prefetch: "SchedulingPrefetch",
    repos: SchedulingRepos,
    default_external_lead_days: int,
    *,
    zone: tzinfo,
) -> list[ExternalWorkChain]:
    """The chain of each lot of `lot_ids`, the lots with open external
    work, from a prefetch that loaded them, for
    scheduling.forecast_external_work once the walk has placed the internal
    orders. Walking each lot's whole chain dates the positions no later
    order of the lot reads, such as the last position of a lot or an
    outsourced one without a supplier."""
    chains: list[ExternalWorkChain] = []
    for lot_id in sorted(lot_ids):
        lot = prefetch.lots_by_id.get(lot_id)
        if lot is None:
            continue
        positions = await describe_lot_chain(
            lot,
            repos,
            prefetch.sibling_orders_by_position,
            prefetch.order_items_by_position,
            default_external_lead_days,
            prefetch.material_ready_at_by_lot,
            zone=zone,
            today=prefetch.today,
        )
        chains.append(
            ExternalWorkChain(
                lot_id=lot.id,
                positions=positions,
                external_position_ids=frozenset(
                    p.id for p in lot.positions if position_has_external_work(p)
                ),
                target_date=prefetch.target_date_by_lot.get(lot.id),
                remaining_minutes_by_position={
                    p.id: remaining_minutes(p, prefetch.sibling_orders_by_position.get(p.id, []))
                    for p in lot.positions
                },
            )
        )
    return chains


async def resolve_material_ready_at(
    lot: ProductionLot,
    repos: SchedulingRepos,
    cache: dict[int, date | None] | None = None,
    *,
    zone: tzinfo,
    today: date | None = None,
) -> date | None:
    """Raw-material readiness for a sequence-1 position, a day of `zone`.
    None without a linked demand (rework lots), for an unresolvable demand,
    or when no order-item allocation carries a date (stock-fulfilled lots).
    A passed expected delivery counts as `today`, the current day unless
    the caller walks against its own clock. The cache is keyed by lot so a
    lot without a demand caches too."""
    if cache is not None and lot.id in cache:
        return cache[lot.id]
    result = await _resolve_material_ready_at_uncached(
        lot, repos, zone, today if today is not None else today_in(zone)
    )
    if cache is not None:
        cache[lot.id] = result
    return result


async def _resolve_material_ready_at_uncached(
    lot: ProductionLot, repos: SchedulingRepos, zone: tzinfo, today: date
) -> date | None:
    if lot.input_demand_id is None:
        return None
    demand = await repos.source_item_demands.get_by_id(lot.input_demand_id)
    if not demand:
        return None
    allocations = await repos.source_item_allocations.get_by_demand_item_id(demand.id)
    order_item_ids = [a.order_item_id for a in allocations if a.order_item_id is not None]
    if not order_item_ids:
        return None
    order_items = await repos.order_items.get_by_ids(order_item_ids)
    return resolve_input_material_ready_at(
        [(oi.delivery_date, oi.expected_delivery_date) for oi in order_items],
        zone=zone,
        today=today,
    )


def _lifecycle_context(
    order: ProductionOrder, lot: ProductionLot, ctx: OrderSchedulingContext
) -> ProductionOrderContext:
    """The context the production order intent table judges the order in:
    its lot's hold and terminal state, whether a machine can be settled on
    (a machine or pool is set, or the step needs none) and whether upstream
    made pieces available."""
    return production_order_rules.production_order_context(
        order,
        lot_held=lot.status == LotStatus.ON_HOLD,
        lot_terminal=lot.status in TERMINAL_LOT_STATUSES,
        machine_resolvable=(
            order.machine_id is not None or order.machine_pool_id is not None or ctx.is_manual_step
        ),
        input_available=ctx.upstream_input_available,
    )


def _resolve_can_start(
    order: ProductionOrder, lot: ProductionLot, ctx: OrderSchedulingContext
) -> bool:
    """Whether the start or the resume rule of the production order intent
    table accepts the order on state grounds. Permissions are excluded,
    because they differ per user. Only a hint; the use case stays the
    enforcer."""
    context = _lifecycle_context(order, lot, ctx)
    for action in (LifecycleAction.START, LifecycleAction.RESUME):
        rule = PRODUCTION_ORDER_INTENTS.rule_for(action)
        if rule is not None and rule.state_allows(order, context):
            return True
    return False


async def _resolve_raw_material_arrived(
    lot: ProductionLot,
    repos: SchedulingRepos,
    cache: dict[int, float] | None = None,
) -> float:
    """The arrived raw-material quantity gating a sequence-1 position,
    resolved like Start does: 0.0 without a linked demand, never
    unconstrained."""
    if lot.input_demand_id is None:
        return 0.0
    if cache is not None and lot.input_demand_id in cache:
        return cache[lot.input_demand_id]
    arrived = await repos.lots.get_raw_material_arrived_quantity(lot.input_demand_id)
    if cache is not None:
        cache[lot.input_demand_id] = arrived
    return arrived


async def _prefetch_sibling_orders_by_position(
    lots: list[ProductionLot], repos: SchedulingRepos
) -> dict[int, list[ProductionOrder]]:
    """Production orders of every position across the lots, in one query."""
    position_ids = [p.id for lot in lots for p in lot.positions]
    if not position_ids:
        return {}
    orders = await repos.orders.get_by_lot_position_ids(position_ids)
    grouped: dict[int, list[ProductionOrder]] = {}
    for o in orders:
        grouped.setdefault(o.lot_position_id, []).append(o)
    return grouped


async def _prefetch_order_items_by_position(
    lots: list[ProductionLot], repos: SchedulingRepos
) -> dict[int, OrderItem]:
    """The newest live order line of every position across the lots, in one
    query, as get_by_lot_position_id reads it. Canceled lines beside it
    supply nothing, and earlier lines closed short have delivered what they
    will."""
    position_ids = [p.id for lot in lots for p in lot.positions]
    if not position_ids:
        return {}
    order_items = await repos.order_items.get_by_lot_position_ids(position_ids)
    return {
        oi.lot_position_id: oi
        for oi in sorted(order_items, key=lambda item: item.id)
        if oi.lot_position_id is not None and oi.canceled_at is None
    }


async def _prefetch_order_item_ids_by_demand(
    demand_ids: list[int], repos: SchedulingRepos
) -> dict[int, list[int]]:
    """The order item ids allocated to each of `demand_ids` that resolves to
    an existing demand, in two queries. A demand that cannot be found has no
    entry, one without order-item-backed allocations maps to an empty list."""
    found_demand_ids = [d.id for d in await repos.source_item_demands.get_by_ids(demand_ids)]
    order_item_ids_by_demand: dict[int, list[int]] = {d: [] for d in found_demand_ids}
    if not found_demand_ids:
        return order_item_ids_by_demand
    for allocation in await repos.source_item_allocations.get_by_demand_item_ids(found_demand_ids):
        if allocation.order_item_id is not None:
            order_item_ids_by_demand[allocation.demand_item_id].append(allocation.order_item_id)
    return order_item_ids_by_demand


async def _prefetch_material_ready_at_by_lot(
    lots: list[ProductionLot], repos: SchedulingRepos, zone: tzinfo, today: date
) -> dict[int, date | None]:
    """resolve_material_ready_at for every lot, in three queries."""
    result: dict[int, date | None] = {lot.id: None for lot in lots}
    demand_ids = sorted({lot.input_demand_id for lot in lots if lot.input_demand_id is not None})
    if not demand_ids:
        return result
    order_item_ids_by_demand = await _prefetch_order_item_ids_by_demand(demand_ids, repos)
    all_order_item_ids = sorted({i for ids in order_item_ids_by_demand.values() for i in ids})
    order_items_by_id = (
        {oi.id: oi for oi in await repos.order_items.get_by_ids(all_order_item_ids)}
        if all_order_item_ids
        else {}
    )
    for lot in lots:
        if lot.input_demand_id is None:
            continue
        order_item_ids = order_item_ids_by_demand.get(lot.input_demand_id)
        if not order_item_ids:
            continue
        order_items = [order_items_by_id[i] for i in order_item_ids if i in order_items_by_id]
        result[lot.id] = resolve_input_material_ready_at(
            [(oi.delivery_date, oi.expected_delivery_date) for oi in order_items],
            zone=zone,
            today=today,
        )
    return result


def _gates_on_raw_material(lot: ProductionLot) -> bool:
    """Whether some position of `lot` reads the raw-material arrived
    quantity in _resolve_upstream_input_available: a linked demand, not an
    alteration lot, and an INTERNAL/MIXED position at sequence 1."""
    return (
        lot.input_demand_id is not None
        and not lot.is_alteration
        and any(
            p.sequence == 1 and p.kind in (LotPositionKind.INTERNAL, LotPositionKind.MIXED)
            for p in lot.positions
        )
    )


@dataclass
class SchedulingPrefetch:
    """Every lookup the context builders need, loaded once per batch."""

    lots_by_id: dict[int, ProductionLot | None]
    sibling_orders_by_position: dict[int, list[ProductionOrder]]
    order_items_by_position: dict[int, OrderItem]
    target_date_by_lot: dict[int, date | None]
    material_ready_at_by_lot: dict[int, date | None]
    raw_material_arrived_by_demand: dict[int, float]
    pools_by_id: dict[int, MachinePool | None]
    # The day of the tenant's timezone the prefetch counted a passed
    # expected arrival as, so every context built from it agrees.
    today: date


async def prefetch_scheduling_data(
    orders: list[ProductionOrder],
    repos: SchedulingRepos,
    pool_repo: IMachinePoolRepository | None = None,
    lots_by_id: dict[int, ProductionLot] | None = None,
    extra_lot_ids: Iterable[int] = (),
    *,
    zone: tzinfo,
    today: date | None = None,
) -> SchedulingPrefetch:
    """Loads everything build_order_context reads for the active orders in
    a fixed number of queries. `lots_by_id` pre-seeds lots the caller holds,
    `extra_lot_ids` adds lots no active order belongs to, such as the lots
    of external work, and material readiness is a day of `zone`. A passed
    expected arrival counts as `today`, the current day of `zone` unless
    the caller walks against its own clock."""
    if today is None:
        today = today_in(zone)
    active = [o for o in orders if o.status in ACTIVE_PRODUCTION_ORDER_STATUSES]
    lot_cache: dict[int, ProductionLot | None] = dict(lots_by_id or {})
    wanted_lot_ids = {o.lot_id for o in active} | set(extra_lot_ids)
    missing_lot_ids = sorted(lot_id for lot_id in wanted_lot_ids if lot_id not in lot_cache)
    if missing_lot_ids:
        fetched = {lot.id: lot for lot in await repos.lots.get_by_ids(missing_lot_ids)}
        for lot_id in missing_lot_ids:
            lot_cache[lot_id] = fetched.get(lot_id)
    lots_loaded = [lot for lot in lot_cache.values() if lot is not None]

    sibling_orders_by_position = await _prefetch_sibling_orders_by_position(lots_loaded, repos)
    order_items_by_position = await _prefetch_order_items_by_position(lots_loaded, repos)
    target_dates = await describe_lot_target_dates(lots_loaded, repos)
    material_ready_at_by_lot = await _prefetch_material_ready_at_by_lot(
        lots_loaded, repos, zone, today
    )

    arrived_demand_ids = sorted(
        {
            lot.input_demand_id
            for lot in lots_loaded
            if lot.input_demand_id is not None and _gates_on_raw_material(lot)
        }
    )
    raw_material_arrived_by_demand = (
        await repos.lots.get_raw_material_arrived_quantities(arrived_demand_ids)
        if arrived_demand_ids
        else {}
    )

    pools_by_id: dict[int, MachinePool | None] = {}
    pool_ids = sorted({o.machine_pool_id for o in active if o.machine_pool_id is not None})
    if pool_repo is not None and pool_ids:
        fetched_pools = {p.id: p for p in await pool_repo.get_by_ids(pool_ids)}
        pools_by_id = {pool_id: fetched_pools.get(pool_id) for pool_id in pool_ids}

    return SchedulingPrefetch(
        lots_by_id=lot_cache,
        sibling_orders_by_position=sibling_orders_by_position,
        order_items_by_position=order_items_by_position,
        target_date_by_lot={lot_id: entry[0] for lot_id, entry in target_dates.items()},
        material_ready_at_by_lot=material_ready_at_by_lot,
        raw_material_arrived_by_demand=raw_material_arrived_by_demand,
        pools_by_id=pools_by_id,
        today=today,
    )


# How far ahead future downtimes are fetched for calendars.
_DOWNTIME_CALENDAR_HORIZON_DAYS = 366


async def holiday_dates(calendar_repo: IMachineCalendarRepository) -> frozenset[date]:
    """Every date a tenant holiday closes the plant on."""
    return frozenset(d for holiday in await calendar_repo.get_holidays() for d in holiday.dates())


async def build_machine_calendars(
    machine_ids: list[int],
    calendar_repo: IMachineCalendarRepository,
    default_weekly_hours: Mapping[int, DayHours],
    downtime_repo: IMachineDowntimeRepository | None = None,
    now: datetime | None = None,
    *,
    zone: tzinfo = UTC,
    holidays: frozenset[date] | None = None,
) -> dict[int, MachineCalendar]:
    """Every machine's calendar in batch queries, its hours local to
    `zone`; machines without their own hours use `default_weekly_hours`,
    and the tenant holidays close their days under the exceptions; they
    are read unless the caller passes them.

    With downtime_repo, open and upcoming downtimes are subtracted."""
    if not machine_ids:
        return {}
    working_hours_by_machine_id = {
        wh.machine_id: wh
        for wh in await calendar_repo.get_working_hours_by_machine_ids(machine_ids)
    }
    if holidays is None:
        holidays = await holiday_dates(calendar_repo)
    exceptions_by_machine_id: dict[int, list[MachineCalendarException]] = {}
    for exception in await calendar_repo.get_exceptions_by_machine_ids(machine_ids):
        exceptions_by_machine_id.setdefault(exception.machine_id, []).append(exception)
    calendars = {
        machine_id: build_machine_calendar(
            default_weekly_hours,
            (
                working_hours_by_machine_id[machine_id].weekly_hours
                if machine_id in working_hours_by_machine_id
                else None
            ),
            {e.exception_date: e.hours for e in exceptions_by_machine_id.get(machine_id, [])},
            zone=zone,
            holidays=holidays,
        )
        for machine_id in machine_ids
    }
    if downtime_repo is None:
        return calendars
    resolved_now = now or now_utc()
    horizon_end = resolved_now + timedelta(days=_DOWNTIME_CALENDAR_HORIZON_DAYS)
    downtimes_by_machine_id: dict[int, list[MachineDowntime]] = {}
    for downtime in await downtime_repo.get_overlapping(machine_ids, resolved_now, horizon_end):
        downtimes_by_machine_id.setdefault(downtime.machine_id, []).append(downtime)
    return {
        machine_id: (
            apply_downtimes(calendar, downtimes_by_machine_id[machine_id], resolved_now)
            if machine_id in downtimes_by_machine_id
            else calendar
        )
        for machine_id, calendar in calendars.items()
    }


async def _resolve_position_ready_dates(
    position: LotPosition | None,
    lot: ProductionLot,
    repos: SchedulingRepos,
    sibling_orders_by_position: dict[int, list[ProductionOrder]] | None,
    order_items_by_position: dict[int, OrderItem] | None,
    response_time_days: int,
    default_external_lead_days: int,
    material_ready_at_cache: dict[int, date | None] | None,
    zone: tzinfo,
    today: date,
) -> tuple[date | None, bool, tuple[PredecessorPosition, ...], date | None]:
    """The predecessor and material ready days in `zone`, with the response
    time added to every arrival, plus the predecessor snapshot for the
    propagated walk."""
    predecessor_ready_at = None
    predecessor_chain_unknown = False
    predecessor_positions: tuple[PredecessorPosition, ...] = ()
    if position is not None and position.sequence > 1:
        predecessor_positions = await describe_predecessor_positions(
            position,
            lot,
            repos,
            sibling_orders_by_position,
            order_items_by_position,
            default_external_lead_days,
            material_ready_at_cache,
            zone=zone,
            today=today,
        )
        predecessor_ready_at, predecessor_chain_unknown = stored_predecessor_readiness(
            predecessor_positions, response_time_days
        )

    material_ready_at = None
    if position is not None and position.sequence == 1:
        material_ready_at = await resolve_material_ready_at(
            lot, repos, material_ready_at_cache, zone=zone, today=today
        )
        if material_ready_at is not None:
            material_ready_at += timedelta(days=response_time_days)

    return predecessor_ready_at, predecessor_chain_unknown, predecessor_positions, material_ready_at


def _resolve_capability_mismatch(
    order: ProductionOrder,
    machine: ProductionMachine | None,
    pool: MachinePool | None,
    steps: list[LotStep],
) -> bool:
    """Whether the order's machine, or its pool while unresolved, no longer
    covers the position's steps, for example after a pool membership edit.
    Unexpected errors are logged and re-raised rather than shown as a badge."""
    if machine is not None:
        try:
            assert_capability_match(machine, steps)
        except MachineCapabilityMismatchError:
            return True
        except Exception:
            log.exception(
                "Capability check failed for order #%s on machine #%s.", order.id, machine.id
            )
            raise
    elif pool is not None:
        try:
            assert_pool_capability_match(pool, steps)
        except MachineCapabilityMismatchError:
            return True
        except Exception:
            log.exception("Capability check failed for order #%s on pool #%s.", order.id, pool.id)
            raise
    return False


async def _resolve_upstream_input_available(
    position: LotPosition | None,
    lot: ProductionLot,
    repos: SchedulingRepos,
    raw_material_arrived_by_demand: dict[int, float] | None,
) -> bool:
    """Mirrors lot_rules.assert_position_has_available_input exactly, so the
    badge and can_start say what Start enforces."""
    if position is None:
        return True
    raw_material_arrived = None
    if (
        position.sequence == 1
        and position.kind in (LotPositionKind.INTERNAL, LotPositionKind.MIXED)
        and not lot.is_alteration
    ):
        raw_material_arrived = await _resolve_raw_material_arrived(
            lot, repos, raw_material_arrived_by_demand
        )
    return quantity_gt(open_input(position, lot.positions, lot.quantity, raw_material_arrived), 0.0)


async def _resolve_position_not_fully_queued(
    position: LotPosition | None,
    repos: SchedulingRepos,
    sibling_orders_by_position: dict[int, list[ProductionOrder]] | None,
) -> bool:
    """True when the queued orders do not yet cover the position quantity."""
    if position is None:
        return False
    sibling_orders = (
        sibling_orders_by_position.get(position.id, [])
        if sibling_orders_by_position is not None
        else await repos.orders.get_by_lot_position_id(position.id)
    )
    return not is_position_fully_queued(sibling_orders, position.quantity)


async def build_order_context(
    order: ProductionOrder,
    lot: ProductionLot,
    machine: ProductionMachine | None,
    repos: SchedulingRepos,
    target_date: date | None,
    sibling_orders_by_position: dict[int, list[ProductionOrder]] | None = None,
    response_time_days: int = 0,
    raw_material_arrived_by_demand: dict[int, float] | None = None,
    order_items_by_position: dict[int, OrderItem] | None = None,
    pool: MachinePool | None = None,
    default_external_lead_days: int = 0,
    material_ready_at_cache: dict[int, date | None] | None = None,
    machine_down: bool = False,
    internal_handoff_minutes: int = 0,
    *,
    zone: tzinfo,
    today: date | None = None,
) -> OrderSchedulingContext:
    """Flattens one order and its lot into an OrderSchedulingContext whose
    days are days of the tenant's timezone `zone`. A passed expected arrival
    counts as `today`, the current day unless the caller walks against its
    own clock.

    response_time_days buffers an external predecessor's and the raw
    material's arrival but never not_before, a deliberate planner override,
    and internal_handoff_minutes the end of an in-house predecessor;
    read-only callers pass 0 for both.
    Without `pool`, a pool-assigned order's capability goes unchecked."""
    position = next((p for p in lot.positions if p.id == order.lot_position_id), None)
    steps = position.steps if position else []

    (
        predecessor_ready_at,
        predecessor_chain_unknown,
        predecessor_positions,
        material_ready_at,
    ) = await _resolve_position_ready_dates(
        position,
        lot,
        repos,
        sibling_orders_by_position,
        order_items_by_position,
        response_time_days,
        default_external_lead_days,
        material_ready_at_cache,
        zone,
        today if today is not None else today_in(zone),
    )

    capability_mismatch = _resolve_capability_mismatch(order, machine, pool, steps)

    position_not_fully_queued = await _resolve_position_not_fully_queued(
        position, repos, sibling_orders_by_position
    )
    time_estimate_source = production_order_rules.estimate_time_source(steps)
    is_manual_step = position_is_manual(steps)

    upstream_input_available = await _resolve_upstream_input_available(
        position, lot, repos, raw_material_arrived_by_demand
    )
    position_sequence = position.sequence if position is not None else 1

    return OrderSchedulingContext(
        order_id=order.id,
        queue_sequence=order.queue_sequence,
        status=order.status,
        pinned=order.pinned,
        estimated_duration_minutes=order.estimated_duration_minutes,
        not_before=order.not_before,
        actual_start=order.actual_start,
        existing_planned_start=order.planned_start,
        existing_planned_end=order.planned_end,
        predecessor_ready_at=predecessor_ready_at,
        material_ready_at=material_ready_at,
        target_date=target_date,
        capability_mismatch=capability_mismatch,
        # Fabrication methods are a flat catalogue, so a step can never be uncategorized.
        uncategorized_step=False,
        position_not_fully_queued=position_not_fully_queued,
        time_estimate_source=time_estimate_source,
        is_manual_step=is_manual_step,
        upstream_input_available=upstream_input_available,
        position_sequence=position_sequence,
        predecessor_chain_unknown=predecessor_chain_unknown,
        machine_pool_id=order.machine_pool_id,
        lot_id=lot.id,
        lot_position_id=position.id if position is not None else None,
        predecessor_positions=predecessor_positions,
        response_time_days=response_time_days,
        internal_handoff_minutes=internal_handoff_minutes,
        wait_after_minutes=(
            position_wait_after_minutes(position.kind, step_waits(steps))
            if position is not None
            else 0
        ),
        quantity=order.quantity,
        pieces_processed=order.pieces_processed,
        pieces_processed_at_resume=_pieces_processed_at_resume(order),
        minutes_per_piece=sum(
            production_order_rules.resolve_effective_per_piece_minutes(step)[0] for step in steps
        ),
        # From persisted dates; the propagated walk re-derives it every pass.
        stale_external_predecessor=stale_external_predecessor(predecessor_positions, None),
        predecessor_ready_moment=predecessor_ready_moment(
            predecessor_positions, None, internal_handoff_minutes
        ),
        machine_down=machine_down,
        last_resumed_at=last_resumed_at(order.interruptions),
        zone=zone,
    )


def _pieces_processed_at_resume(order: ProductionOrder) -> float:
    """The pieces the order had processed when it last went back to work,
    from the completions recorded before that resume; 0 before any resume."""
    resumed = last_resumed_at(order.interruptions)
    if resumed is None:
        return 0.0
    return sum((c.quantity for c in order.completions if as_utc(c.created) <= as_utc(resumed)), 0.0)


async def _resolve_pool(
    machine_pool_id: int | None,
    pool_repo: IMachinePoolRepository | None,
    pool_cache: dict[int, MachinePool | None],
) -> MachinePool | None:
    """Cached pool lookup, one fetch per distinct pool. Without pool_repo
    the pool is unknown."""
    if machine_pool_id is None or pool_repo is None:
        return None
    if machine_pool_id not in pool_cache:
        pool_cache[machine_pool_id] = await pool_repo.get_by_id(machine_pool_id)
    return pool_cache[machine_pool_id]


async def build_contexts(
    orders: list[ProductionOrder],
    repos: SchedulingRepos,
    machine: ProductionMachine | None = None,
    response_time_days: int = 0,
    pool_repo: IMachinePoolRepository | None = None,
    default_external_lead_days: int = 0,
    down_machine_ids: set[int] | None = None,
    prefetch: SchedulingPrefetch | None = None,
    internal_handoff_minutes: int = 0,
    *,
    zone: tzinfo,
    today: date | None = None,
) -> list[OrderSchedulingContext]:
    """One OrderSchedulingContext per active order, its days in the
    tenant's timezone `zone`. `prefetch` may cover a superset of `orders`
    and must have been built in the same zone; without it one is built for
    them. A passed expected arrival counts as `today`, else as the day the
    prefetch counted it as."""
    down_ids = down_machine_ids or set()
    active = [o for o in orders if o.status in ACTIVE_PRODUCTION_ORDER_STATUSES]
    if prefetch is None:
        prefetch = await prefetch_scheduling_data(active, repos, pool_repo, zone=zone, today=today)
    target_date_cache = dict(prefetch.target_date_by_lot)
    pool_cache = dict(prefetch.pools_by_id)
    material_ready_at_cache = dict(prefetch.material_ready_at_by_lot)
    raw_material_arrived_by_demand = dict(prefetch.raw_material_arrived_by_demand)

    contexts = []
    for order in active:
        lot = prefetch.lots_by_id.get(order.lot_id)
        if lot is None:
            continue
        if order.lot_id not in target_date_cache:
            target_date_cache[order.lot_id] = await resolve_lot_target_date(lot, repos)
        contexts.append(
            await build_order_context(
                order,
                lot,
                machine,
                repos,
                target_date_cache[order.lot_id],
                prefetch.sibling_orders_by_position,
                response_time_days,
                raw_material_arrived_by_demand,
                prefetch.order_items_by_position,
                pool=await _resolve_pool(order.machine_pool_id, pool_repo, pool_cache),
                default_external_lead_days=default_external_lead_days,
                material_ready_at_cache=material_ready_at_cache,
                machine_down=order.machine_id in down_ids,
                internal_handoff_minutes=internal_handoff_minutes,
                zone=zone,
                today=today if today is not None else prefetch.today,
            )
        )
    return contexts


async def _build_order_contexts(
    orders: list[ProductionOrder],
    repos: SchedulingRepos,
    machine_repo: IProductionMachineRepository,
    lots_by_id: dict[int, ProductionLot] | None = None,
    pool_repo: IMachinePoolRepository | None = None,
    *,
    zone: tzinfo,
) -> dict[int, tuple[ProductionLot, OrderSchedulingContext]]:
    """Contexts for the plain-read paths, keyed by order, their days in
    `zone`. Terminal orders and orders without a resolvable lot have no
    entry. `lots_by_id` pre-seeds lots the caller already holds, so a page
    of lots is not fetched again."""
    prefetch = await prefetch_scheduling_data(orders, repos, pool_repo, lots_by_id, zone=zone)
    machine_ids = sorted(
        {
            o.machine_id
            for o in orders
            if o.status in ACTIVE_PRODUCTION_ORDER_STATUSES
            and o.machine_id is not None
            and prefetch.lots_by_id.get(o.lot_id) is not None
        }
    )
    fetched_machines = (
        {m.id: m for m in await machine_repo.get_by_ids(machine_ids)} if machine_ids else {}
    )
    machine_cache: dict[int, ProductionMachine | None] = {
        machine_id: fetched_machines.get(machine_id) for machine_id in machine_ids
    }
    pool_cache = dict(prefetch.pools_by_id)
    target_date_cache = dict(prefetch.target_date_by_lot)
    raw_material_arrived_by_demand = dict(prefetch.raw_material_arrived_by_demand)
    material_ready_at_cache = dict(prefetch.material_ready_at_by_lot)
    result: dict[int, tuple[ProductionLot, OrderSchedulingContext]] = {}

    for order in orders:
        if order.status not in ACTIVE_PRODUCTION_ORDER_STATUSES:
            continue

        lot = prefetch.lots_by_id.get(order.lot_id)
        if lot is None:
            continue

        result[order.id] = await _build_one_order_context(
            order,
            lot,
            repos,
            machine_repo,
            machine_cache,
            pool_cache,
            pool_repo,
            target_date_cache,
            prefetch.sibling_orders_by_position,
            prefetch.order_items_by_position,
            raw_material_arrived_by_demand,
            material_ready_at_cache,
            zone,
            prefetch.today,
        )

    return result


async def _build_one_order_context(
    order: ProductionOrder,
    lot: ProductionLot,
    repos: SchedulingRepos,
    machine_repo: IProductionMachineRepository,
    machine_cache: dict[int, ProductionMachine | None],
    pool_cache: dict[int, MachinePool | None],
    pool_repo: IMachinePoolRepository | None,
    target_date_cache: dict[int, date | None],
    sibling_orders_by_position: dict[int, list[ProductionOrder]],
    order_items_by_position: dict[int, OrderItem],
    raw_material_arrived_by_demand: dict[int, float],
    material_ready_at_cache: dict[int, date | None],
    zone: tzinfo,
    today: date,
) -> tuple[ProductionLot, OrderSchedulingContext]:
    """One order's (lot, context) pair, filling the caches on first use."""
    machine = None
    if order.machine_id is not None:
        if order.machine_id not in machine_cache:
            machine_cache[order.machine_id] = await machine_repo.get_by_id(order.machine_id)
        machine = machine_cache[order.machine_id]

    if order.lot_id not in target_date_cache:
        target_date_cache[order.lot_id] = await resolve_lot_target_date(lot, repos)

    ctx = await build_order_context(
        order,
        lot,
        machine,
        repos,
        target_date_cache[order.lot_id],
        sibling_orders_by_position,
        raw_material_arrived_by_demand=raw_material_arrived_by_demand,
        order_items_by_position=order_items_by_position,
        pool=await _resolve_pool(order.machine_pool_id, pool_repo, pool_cache),
        material_ready_at_cache=material_ready_at_cache,
        zone=zone,
        today=today,
    )
    return lot, ctx


async def _fill_actions_without_context(
    orders: list[ProductionOrder],
    repos: SchedulingRepos,
    lots_by_id: dict[int, ProductionLot] | None,
    actor: User,
) -> None:
    """Actions of orders the scheduling context skips, terminal ones in
    particular. A completed order can still have a completion reversed, so
    the intent table judges it from its lot's hold and terminal state; the
    machine and input conditions only gate starting, which no terminal
    order offers. An order whose lot cannot be read keeps no actions."""
    known = dict(lots_by_id or {})
    missing = sorted({o.lot_id for o in orders if o.lot_id not in known})
    if missing:
        known.update({lot.id: lot for lot in await repos.lots.get_by_ids(missing)})
    for order in orders:
        lot = known.get(order.lot_id)
        if lot is None:
            order.actions = []
            continue
        context = production_order_rules.production_order_context(
            order,
            lot_held=lot.status == LotStatus.ON_HOLD,
            lot_terminal=lot.status in TERMINAL_LOT_STATUSES,
        )
        order.actions = [
            action.value
            for action in PRODUCTION_ORDER_INTENTS.allowed_actions(order, context, actor)
        ]


async def compute_conflicts_for_orders(
    orders: list[ProductionOrder],
    repos: SchedulingRepos,
    machine_repo: IProductionMachineRepository,
    lots_by_id: dict[int, ProductionLot] | None = None,
    pool_repo: IMachinePoolRepository | None = None,
    actor: User | None = None,
) -> dict[int, list[str]]:
    """Conflicts for a batch of orders from persisted state, without a
    calendar walk. Shared by every read path so an order's conflicts look
    the same everywhere. Terminal orders get an empty list. Each order's
    can_start is set as a side effect, and with an actor its actions, the
    ones the production order intent table allows that actor now. An order
    without a scheduling context, a completed one for instance, still gets
    its actions, judged from its lot alone. Days are compared in the
    tenant's timezone."""
    now = now_utc()
    built = await _build_order_contexts(
        orders, repos, machine_repo, lots_by_id, pool_repo, zone=await tenant_zone(repos.settings)
    )
    result: dict[int, list[str]] = {}
    unbuilt = [o for o in orders if o.id not in built]
    if actor is not None and unbuilt:
        await _fill_actions_without_context(unbuilt, repos, lots_by_id, actor)

    for order in orders:
        entry = built.get(order.id)
        if entry is None:
            result[order.id] = []
            continue

        lot, ctx = entry
        conflicts = compute_order_conflicts(ctx, order.planned_end, now)
        # A pool assignment is a planner decision, not a missing machine.
        if order.machine_id is None and order.machine_pool_id is None and not ctx.is_manual_step:
            conflicts = [*conflicts, ScheduleConflictReason.NO_MACHINE_ASSIGNED.value]
        result[order.id] = conflicts
        order.can_start = _resolve_can_start(order, lot, ctx)
        if actor is not None:
            context = _lifecycle_context(order, lot, ctx)
            order.actions = [
                action.value
                for action in PRODUCTION_ORDER_INTENTS.allowed_actions(order, context, actor)
            ]

    return result


async def compute_schedule_explanations_for_orders(
    orders: list[ProductionOrder],
    repos: SchedulingRepos,
    machine_repo: IProductionMachineRepository,
    lots_by_id: dict[int, ProductionLot] | None = None,
    pool_repo: IMachinePoolRepository | None = None,
) -> dict[int, EarliestStartExplanation]:
    """What governs each order's earliest start, from the same contexts as
    compute_conflicts_for_orders. Orders without a context have no entry. A
    manual order without a machine waits behind no other order, so its
    start is never explained by a queue."""
    built = await _build_order_contexts(
        orders, repos, machine_repo, lots_by_id, pool_repo, zone=await tenant_zone(repos.settings)
    )
    machineless_ids = {o.id for o in orders if o.machine_id is None and o.machine_pool_id is None}
    return {
        order_id: explain_earliest_start(
            ctx, on_queue=not (ctx.is_manual_step and order_id in machineless_ids)
        )
        for order_id, (_lot, ctx) in built.items()
    }
