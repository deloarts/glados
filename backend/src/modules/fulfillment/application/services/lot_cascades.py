"""Top-down cascades onto a lot's live work: the cancel of a lot, which a
disposition that leaves the lot with nothing to produce shares, and the
close of a force-completed lot, plus the settling of the lot's raw material
demand. The lot lifecycle use cases and piece_disposition.py run the
cascades, and the production order locks and the goods receipt of order
lines take their lock targets from lot_work_lock_targets as well.

The cascades skip the per-order ownership checks: canceling or
force-completing a lot needs manage:lots and acts on other users' orders,
and a disposition acts for the use case that authorized it. They record
facts and intents only and register the production orders and order lines
they wrote with the caller's lifecycle reconciler, which derives the
statuses of the orders, the lines, the lines' orders, the positions and the
lot, and publishes their events, when the caller runs it.

Canceling cancels every live production order and every live line with
nothing delivered or lost, and closes a line that has pieces delivered or
lost short at those pieces, so the supplier sends nothing more. Closing a
force-completed lot keeps what was done: a production order stops at the
pieces it processed and is canceled when it processed none, and a line is
closed short at its delivered and lost pieces and canceled when it has
none. Neither books a piece nobody made or received.

A canceled or force-completed lot settles its raw material demand
(settle_input_demand): a demand nothing of which is placed or arrived is
canceled, which releases its allocations; any other is fulfilled by hand at
what arrived, and its allocations on supplier lines that still wait for
pieces are cut to the pieces that reached them, so the rest of those lines
is free capacity and a later delivery does not land on a closed demand. The
lines themselves stay open, since the supplier was ordered; the caller
names them to purchasing.

The caller locks the lot first and then, in one acquisition, the rows a
cascade may write (lot_work_lock_targets): the production orders, the live
lines with their orders and every demand the cascade or the reconciler
writes, so the cascades and the reconciler find them held. The cascades
read the orders, lines and demands again under those locks.
"""

from collections.abc import Iterable
from dataclasses import dataclass
from dataclasses import field
from dataclasses import replace
from datetime import datetime

from src.modules.fulfillment.application.services.allocation_fill import line_fill
from src.modules.fulfillment.application.services.allocation_release import deallocate_order_item
from src.modules.fulfillment.application.services.allocation_release import release_source_demand
from src.modules.fulfillment.application.services.lifecycle_loader import AggregateIds
from src.modules.fulfillment.application.services.lifecycle_reconciler import LifecycleReconciler
from src.modules.fulfillment.application.services.production_order_interruptions import (
    close_open_interruptions,
)
from src.modules.fulfillment.domain.entities.lot_position import LotPosition
from src.modules.fulfillment.domain.entities.order_item import OrderItem
from src.modules.fulfillment.domain.entities.production_lot import ProductionLot
from src.modules.fulfillment.domain.entities.production_order import ProductionOrder
from src.modules.fulfillment.domain.events.lot_events import LotSupplierLinesToSettle
from src.modules.fulfillment.domain.services.lifecycle.demand import SOURCE_FILL_RANK
from src.modules.fulfillment.domain.services.lifecycle.demand import pieces_ahead
from src.modules.fulfillment.domain.services.lot_event_service import build_lot_event
from src.modules.fulfillment.domain.services.lot_rules import line_end_action
from src.modules.fulfillment.domain.services.production_order_rules import (
    compute_estimated_duration_minutes,
)
from src.modules.fulfillment.domain.value_objects.interruption_ended_by import InterruptionEndedBy
from src.modules.fulfillment.domain.value_objects.lifecycle_aggregate import LifecycleAggregate
from src.modules.fulfillment.domain.value_objects.lot_event_type import LotEventType
from src.modules.fulfillment.domain.value_objects.order_status import OrderItemStatus
from src.modules.fulfillment.domain.value_objects.production_status import (
    TERMINAL_PRODUCTION_ORDER_STATUSES,
)
from src.modules.fulfillment.domain.value_objects.source_item_demand_status import (
    SourceItemDemandStatus,
)
from src.modules.fulfillment.ports.outbound.repositories.bought_item_demand_repository import (
    IBoughtItemAllocationRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.order_repository import (
    IOrderItemRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.order_repository import IOrderRepository
from src.modules.fulfillment.ports.outbound.repositories.production_lot_repository import (
    IProductionLotRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.production_order_interruption_repository import (
    IProductionOrderInterruptionRepository,
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
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.services.edit_version import bump_edit_version
from src.modules.platform.domain.services.quantities import is_zero_quantity
from src.modules.platform.domain.services.quantities import quantity_ge
from src.modules.platform.domain.services.quantities import quantity_gt
from src.modules.platform.infrastructure.logging.logger import log
from src.shared_kernel.domain.services.changelog_service import append_changelog
from src.shared_kernel.domain.value_objects.lifecycle_action import LifecycleAction


async def cascade_lock_targets(
    positions: Iterable[LotPosition],
    order_repo: IProductionOrderRepository,
    order_item_repo: IOrderItemRepository,
) -> AggregateIds:
    """The rows a cascade over these positions may write besides the lot:
    their live production orders, and their live lines with the lines'
    orders. A completed or canceled order is never written by a cascade, so
    it is not locked. The caller locks them in one acquisition right after
    the lot, before a cascade runs; it holds the lot's lock while this reads,
    so no order of the lot comes back to life in between."""
    position_ids = sorted({p.id for p in positions})
    if not position_ids:
        return AggregateIds()
    orders = await order_repo.get_by_lot_position_ids(position_ids)
    lines = [
        line
        for line in await order_item_repo.get_by_lot_position_ids(position_ids)
        if line.canceled_at is None
    ]
    return AggregateIds.of(
        {
            LifecycleAggregate.PRODUCTION_ORDERS: {
                o.id for o in orders if o.status not in TERMINAL_PRODUCTION_ORDER_STATUSES
            },
            LifecycleAggregate.ORDERS: {line.order_id for line in lines},
            LifecycleAggregate.ORDER_ITEMS: {line.id for line in lines},
        }
    )


async def lot_work_lock_targets(
    reconciler: LifecycleReconciler,
    lot: ProductionLot,
    order_repo: IProductionOrderRepository,
    order_item_repo: IOrderItemRepository,
) -> AggregateIds:
    """cascade_lock_targets of the lot's positions, plus every demand a
    cascade over the lot may write: the lot and its live lines are touched
    with `reconciler`, whose widening adds the made demands allocated to the
    lot and the demands allocated to the lines to the caller's next
    acquisition, and the lot's raw material demand is added, which
    cancel_input_demand cancels. The caller reads the lot under its lock
    first, so the raw material link is current."""
    targets = await cascade_lock_targets(lot.positions, order_repo, order_item_repo)
    reconciler.touch_lots([lot.id])
    reconciler.touch_order_items(targets.get(LifecycleAggregate.ORDER_ITEMS))
    if lot.input_demand_id is None:
        return targets
    return targets.union(
        AggregateIds.of({LifecycleAggregate.SOURCE_DEMANDS: [lot.input_demand_id]})
    )


async def _working_orders(
    order_repo: IProductionOrderRepository, positions: Iterable[LotPosition]
) -> list[ProductionOrder]:
    """The production orders of the positions that are neither completed
    nor canceled, read again under the caller's locks. An order that has
    processed its quantity counts as completed even before the reconciler
    stored that, as when the caller's own scrap finished it."""
    position_ids = sorted({p.id for p in positions})
    if not position_ids:
        return []
    orders = await order_repo.get_by_lot_position_ids(position_ids, refresh=True)
    return [
        o
        for o in orders
        if o.status not in TERMINAL_PRODUCTION_ORDER_STATUSES
        and not (quantity_gt(o.quantity, 0.0) and quantity_ge(o.pieces_processed, o.quantity))
    ]


async def _live_lines(
    order_item_repo: IOrderItemRepository, positions: Iterable[LotPosition]
) -> list[OrderItem]:
    """The positions' live lines, read again under the caller's locks."""
    position_ids = sorted({p.id for p in positions})
    if not position_ids:
        return []
    lines = await order_item_repo.get_by_lot_position_ids(position_ids, refresh=True)
    return sorted((line for line in lines if line.canceled_at is None), key=lambda i: i.id)


async def cancel_production_order(
    order: ProductionOrder,
    lot: ProductionLot,
    actor: User,
    now: datetime,
    reason: str,
    *,
    lot_repo: IProductionLotRepository,
    order_repo: IProductionOrderRepository,
    interruption_repo: IProductionOrderInterruptionRepository,
    reconciler: LifecycleReconciler,
) -> None:
    """Records the cancel of one production order of the lot: canceled_at,
    its open interruptions closed and a row on the lot's timeline."""
    bump_edit_version(order)
    order.canceled_at = now
    order.changed = now
    order.changes = append_changelog(order.changes, actor.full_name, f"Canceled, {reason}.")
    await order_repo.save(order)
    await close_open_interruptions(
        interruption_repo, order.id, now, actor.id, ended_by=InterruptionEndedBy.CANCEL
    )
    reconciler.touch_production_orders([order.id])
    await lot_repo.record_event(
        build_lot_event(
            lot.id,
            actor,
            LotEventType.ORDER_CANCELED,
            "order",
            f"Production order #{order.id} canceled, {reason}.",
            entity_id=order.id,
            payload={"quantity": order.quantity},
        )
    )


async def cancel_line(
    line: OrderItem,
    actor: User,
    now: datetime,
    reason: str,
    *,
    order_item_repo: IOrderItemRepository,
    reconciler: LifecycleReconciler,
) -> None:
    """Records the cancel of one line: canceled_at."""
    bump_edit_version(line)
    line.canceled_at = now
    line.changed = now
    line.changes = append_changelog(line.changes, actor.full_name, f"Canceled, {reason}.")
    await order_item_repo.save(line)
    reconciler.touch_order_items([line.id])


async def close_line_short_at_settled(
    line: OrderItem,
    actor: User,
    now: datetime,
    reason: str,
    *,
    order_item_repo: IOrderItemRepository,
    reconciler: LifecycleReconciler,
) -> None:
    """Closes one line short at its delivered and lost pieces and records the
    close and the quantity before it. A position's
    line is a MADE line, which no demand allocation draws on, since an
    allocation names a bought or a source item, so there is no allocation
    to shrink with it."""
    old_quantity = line.quantity
    line.quantity = line.quantity_settled
    bump_edit_version(line)
    line.closed_short_at = now
    line.closed_short_from = old_quantity
    line.changed = now
    line.changes = append_changelog(
        line.changes,
        actor.full_name,
        f"Closed short at {line.quantity:.3f} of {old_quantity:.3f} {line.unit}, {reason}.",
    )
    await order_item_repo.save(line)
    reconciler.touch_order_items([line.id])


async def cancel_live_work(
    lot: ProductionLot,
    positions: Iterable[LotPosition],
    actor: User,
    now: datetime,
    *,
    reason: str,
    lot_repo: IProductionLotRepository,
    order_repo: IProductionOrderRepository,
    order_item_repo: IOrderItemRepository,
    parent_order_repo: IOrderRepository,
    interruption_repo: IProductionOrderInterruptionRepository,
    reconciler: LifecycleReconciler,
    allocation_repo: IBoughtItemAllocationRepository | None = None,
    keep_ordered_lines: bool = False,
) -> list[OrderItem]:
    """Cancels the positions' live production orders and their live lines
    with nothing delivered or lost, and closes their lines with pieces
    delivered or lost short at those pieces, by the order item intent
    table; a DELIVERED line stays as it is. With the bought allocation
    repository, as the lot cancel passes it, a canceled line also gives up
    any allocation it holds, and the demands that lost one are registered
    with `reconciler`. With `keep_ordered_lines`, as the lot cancel passes
    it, an ORDERED line with nothing delivered or lost is not canceled
    behind the supplier's back but left open and returned, for the caller
    to name to purchasing; a canceled lot's line takes no delivery."""
    positions = list(positions)
    left_open: list[OrderItem] = []
    for order in await _working_orders(order_repo, positions):
        await cancel_production_order(
            order,
            lot,
            actor,
            now,
            reason,
            lot_repo=lot_repo,
            order_repo=order_repo,
            interruption_repo=interruption_repo,
            reconciler=reconciler,
        )
    for line in await _live_lines(order_item_repo, positions):
        parent = await parent_order_repo.get_by_id(line.order_id)
        if parent is None:
            continue
        action = line_end_action(line, parent.status)
        if (
            keep_ordered_lines
            and action is LifecycleAction.CANCEL
            and line.status == OrderItemStatus.ORDERED
        ):
            left_open.append(line)
            continue
        if action is LifecycleAction.CANCEL:
            if allocation_repo is not None:
                reconciler.touch_demands(
                    LifecycleAggregate.BOUGHT_DEMANDS,
                    await deallocate_order_item(line, allocation_repo),
                )
            await cancel_line(
                line, actor, now, reason, order_item_repo=order_item_repo, reconciler=reconciler
            )
        elif action is LifecycleAction.CLOSE_SHORT:
            await close_line_short_at_settled(
                line, actor, now, reason, order_item_repo=order_item_repo, reconciler=reconciler
            )
    return left_open


async def close_live_work_short(
    lot: ProductionLot,
    positions: Iterable[LotPosition],
    actor: User,
    now: datetime,
    *,
    reason: str,
    lot_repo: IProductionLotRepository,
    order_repo: IProductionOrderRepository,
    order_item_repo: IOrderItemRepository,
    parent_order_repo: IOrderRepository,
    interruption_repo: IProductionOrderInterruptionRepository,
    reconciler: LifecycleReconciler,
) -> list[OrderItem]:
    """Closes the positions' live work at what it did, see the module
    docstring: a production order that processed pieces keeps them as its
    quantity, which completes it, with its duration sized to it, and has its
    open interruptions closed; one that processed none is canceled. A live
    line is closed short at its delivered and lost pieces, or canceled when
    it has none, by the order item intent table. Returns the lines canceled
    although they were ordered, for the caller to name to purchasing."""
    positions = list(positions)
    steps_of = {position.id: position.steps for position in positions}
    for order in await _working_orders(order_repo, positions):
        processed = order.pieces_processed
        if not quantity_gt(processed, 0.0):
            await cancel_production_order(
                order,
                lot,
                actor,
                now,
                reason,
                lot_repo=lot_repo,
                order_repo=order_repo,
                interruption_repo=interruption_repo,
                reconciler=reconciler,
            )
            continue
        old_quantity = order.quantity
        order.quantity = processed
        if steps_of.get(order.lot_position_id):
            order.estimated_duration_minutes = compute_estimated_duration_minutes(
                steps_of[order.lot_position_id], processed
            )
        order.changed = now
        order.changes = append_changelog(
            order.changes,
            actor.full_name,
            f"Closed at the {processed:.3f} processed of {old_quantity:.3f} pieces, {reason}.",
        )
        await order_repo.save(order)
        await close_open_interruptions(
            interruption_repo, order.id, now, actor.id, ended_by=InterruptionEndedBy.CUT
        )
        reconciler.touch_production_orders([order.id])
    canceled_ordered: list[OrderItem] = []
    for line in await _live_lines(order_item_repo, positions):
        parent = await parent_order_repo.get_by_id(line.order_id)
        if parent is None:
            continue
        action = line_end_action(line, parent.status)
        if action is LifecycleAction.CANCEL:
            if line.status == OrderItemStatus.ORDERED:
                canceled_ordered.append(line)
            await cancel_line(
                line, actor, now, reason, order_item_repo=order_item_repo, reconciler=reconciler
            )
        elif action is LifecycleAction.CLOSE_SHORT:
            await close_line_short_at_settled(
                line, actor, now, reason, order_item_repo=order_item_repo, reconciler=reconciler
            )
    return canceled_ordered


_PLACED_LINE = frozenset(
    {
        OrderItemStatus.ORDERED,
        OrderItemStatus.PARTIALLY_DELIVERED,
        OrderItemStatus.DELIVERED,
    }
)
_STILL_OPEN_LINE = frozenset(
    {
        OrderItemStatus.PENDING,
        OrderItemStatus.REQUESTED,
        OrderItemStatus.ORDERED,
        OrderItemStatus.PARTIALLY_DELIVERED,
    }
)


@dataclass(frozen=True)
class InputSettlement:
    """What settling a lot's raw material demand did: the supplier lines
    still open whose allocation was cut, for purchasing, and when the demand
    was fulfilled short, what arrived of it and in which unit."""

    open_lines: list[OrderItem] = field(default_factory=list)
    fulfilled: bool = False
    arrived: float = 0.0
    unit: str = ""


async def settle_input_demand(
    lot: ProductionLot,
    actor: User,
    now: datetime,
    *,
    reason: str,
    source_item_demands: ISourceItemDemandRepository,
    source_allocations: ISourceItemAllocationRepository,
    bought_allocations: IBoughtItemAllocationRepository,
    order_item_repo: IOrderItemRepository,
    reconciler: LifecycleReconciler,
) -> InputSettlement:
    """Settles the lot's raw material demand, see the module docstring, and
    registers it with `reconciler`. Returns what it did; nothing when the
    demand is canceled or was settled already."""
    if lot.input_demand_id is None:
        return InputSettlement()
    demand = await source_item_demands.get_by_id(lot.input_demand_id)
    if (
        demand is None
        or demand.canceled_at is not None
        or demand.fulfilled_manually_at is not None
        or demand.status == SourceItemDemandStatus.FULFILLED
    ):
        return InputSettlement()
    allocations = await source_allocations.get_by_demand_item_id(demand.id)
    lines = {
        line.id: line
        for line in await order_item_repo.get_by_ids(
            sorted({a.order_item_id for a in allocations if a.order_item_id is not None})
        )
    }
    from_stock = any(a.order_item_id is None and quantity_gt(a.quantity, 0.0) for a in allocations)
    committed = from_stock or any(
        line.status in _PLACED_LINE or quantity_gt(line.quantity_delivered, 0.0)
        for line in lines.values()
    )
    if not committed:
        await release_source_demand(demand, source_allocations, actor, now, f"Canceled, {reason}.")
        await source_item_demands.save(demand)
        reconciler.touch_demands(LifecycleAggregate.SOURCE_DEMANDS, [demand.id])
        return InputSettlement()

    fill = await line_fill(lines.keys(), bought=bought_allocations, source=source_allocations)
    arrived = 0.0
    released: list[OrderItem] = []
    for allocation in allocations:
        if allocation.order_item_id is None:
            arrived += allocation.quantity
            continue
        line = lines.get(allocation.order_item_id)
        if line is None or line.status == OrderItemStatus.CANCELED:
            continue
        ahead = pieces_ahead(fill.get(line.id, ()), SOURCE_FILL_RANK, demand.id)
        reached = min(max(line.quantity_delivered - ahead, 0.0), allocation.quantity)
        arrived += reached
        if line.status not in _STILL_OPEN_LINE or not quantity_gt(allocation.quantity, reached):
            continue
        if is_zero_quantity(reached):
            await source_allocations.delete(allocation)
        else:
            await source_allocations.save(replace(allocation, quantity=reached))
        released.append(line)
    demand.fulfilled_manually_at = now
    demand.changed = now
    rest = (
        f"; released the open rest on order line(s) {', '.join(f'#{line.id}' for line in released)}"
        if released
        else ""
    )
    demand.changes = append_changelog(
        demand.changes,
        actor.full_name,
        f"Fulfilled short at {arrived:.3f} of {demand.quantity:.3f} {demand.unit}, {reason}{rest}.",
    )
    await source_item_demands.save(demand)
    reconciler.touch_demands(LifecycleAggregate.SOURCE_DEMANDS, [demand.id])
    return InputSettlement(open_lines=released, fulfilled=True, arrived=arrived, unit=demand.unit)


async def cancel_input_demand(
    source_item_demands: ISourceItemDemandRepository,
    source_allocations: ISourceItemAllocationRepository,
    reconciler: LifecycleReconciler,
    actor: User,
    lot: ProductionLot,
    now: datetime,
    *,
    reason: str,
) -> None:
    """Cancels the lot's raw material demand, which serves only this lot,
    unless its material has arrived: it records the demand's canceled_at and
    releases its allocations, as every demand cancel does, and registers it
    with `reconciler`, which derives CANCELED. The link stays, and the
    changelog line records what was canceled and why."""
    if lot.input_demand_id is None:
        return
    demand = await source_item_demands.get_by_id(lot.input_demand_id)
    if not demand or demand.canceled_at is not None:
        return
    if demand.status in (
        SourceItemDemandStatus.FULFILLED,
        SourceItemDemandStatus.CANCELED,
    ):
        log.info(
            f"Source item demand #{demand.id} of lot {lot.lot_number!r} is already "
            f"{demand.status.value} and is left as it is."
        )
        return

    await release_source_demand(demand, source_allocations, actor, now, f"Canceled, {reason}.")
    await source_item_demands.save(demand)
    reconciler.touch_demands(LifecycleAggregate.SOURCE_DEMANDS, [demand.id])


async def lines_to_settle_event(
    parent_orders: IOrderRepository,
    lot: ProductionLot,
    actor: User,
    *,
    ended: str,
    open_lines: list[OrderItem],
    canceled_lines: list[OrderItem],
) -> LotSupplierLinesToSettle | None:
    """The notice to purchasing of the supplier lines an ended lot left to
    settle: open ones that still expect pieces and ordered ones it
    canceled, each named once by its order number and position. None when
    there are none."""
    open_unique = list({line.id: line for line in open_lines}.values())
    canceled_unique = list({line.id: line for line in canceled_lines}.values())
    if not open_unique and not canceled_unique:
        return None
    numbers: dict[int, str] = {}
    for line in [*open_unique, *canceled_unique]:
        if line.order_id not in numbers:
            order = await parent_orders.get_by_id(line.order_id)
            numbers[line.order_id] = order.order_number if order else f"#{line.order_id}"

    def label(line: OrderItem) -> str:
        return f"{numbers[line.order_id]} pos. {line.position}"

    first = (open_unique or canceled_unique)[0]
    log.info(
        f"Lot {lot.lot_number!r} was {ended.replace('_', '-')} with supplier line(s) to settle: "
        f"{', '.join(label(line) for line in [*open_unique, *canceled_unique])}."
    )
    return LotSupplierLinesToSettle(
        lot_id=lot.id,
        lot_number=lot.lot_number,
        ended=ended,
        open_lines=[label(line) for line in open_unique],
        canceled_lines=[label(line) for line in canceled_unique],
        order_id=first.order_id,
        actor_id=actor.id,
    )
