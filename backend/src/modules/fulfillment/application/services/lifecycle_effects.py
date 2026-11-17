"""
The events and lot timeline rows the lifecycle reconciler publishes for the
status changes it wrote, one entry per aggregate. A change publishes the event
its consumers already listen for: a lot publishes LotStatusChanged on every
change and LotCompleted besides when it becomes COMPLETED, a lot position
publishes LotPositionStatusChanged, a production order publishes
ProductionOrderStatusChanged on every change and, when it becomes COMPLETED or
CANCELED, ProductionOrderCompleted or ProductionOrderCanceled besides, an
order line publishes OrderItemStatusChanged and an order OrderStatusChanged
on every change, and a demand of each family publishes its status changed
event on every change: DemandItemStatusChanged, MadeItemDemandItemStatusChanged
and SourceItemDemandStatusChanged, and a quote request publishes
QuoteRequestStatusChanged on every change.

A lot status change also gets a row on the lot's timeline, unless the intent
behind it records its own: a cancel, a hold and a resume write their rows in
the use cases that record them, and so does a force-complete, whose row
alone starts with "Lot force-completed". The reconciler writes LOT_COMPLETED
when the facts complete the lot, LOT_SCRAPPED when nothing is left to
produce and LOT_STATUS_CHANGED for every other change.

A bought demand that becomes FULFILLED names the order line that delivered
it, so the delivery mail can show it: the touched line among the demand's
allocations, the newest one if there are several.
"""

from collections.abc import Callable
from collections.abc import Iterable
from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum

from src.modules.catalogue.domain.events.bought_item_events import DemandItemStatusChanged
from src.modules.catalogue.domain.events.made_item_events import MadeItemDemandItemStatusChanged
from src.modules.catalogue.domain.value_objects.bought_item_status import BoughtItemDemandStatus
from src.modules.catalogue.domain.value_objects.made_item_status import MadeItemDemandStatus
from src.modules.fulfillment.domain.entities.lot_event import LotEvent
from src.modules.fulfillment.domain.entities.lot_position import LotPosition
from src.modules.fulfillment.domain.entities.production_lot import ProductionLot
from src.modules.fulfillment.domain.entities.source_item_demand_item import SourceItemDemandItem
from src.modules.fulfillment.domain.events.lot_events import LotCompleted
from src.modules.fulfillment.domain.events.lot_events import LotPositionStatusChanged
from src.modules.fulfillment.domain.events.lot_events import LotStatusChanged
from src.modules.fulfillment.domain.events.order_events import OrderItemStatusChanged
from src.modules.fulfillment.domain.events.order_events import OrderStatusChanged
from src.modules.fulfillment.domain.events.production_order_events import ProductionOrderCanceled
from src.modules.fulfillment.domain.events.production_order_events import ProductionOrderCompleted
from src.modules.fulfillment.domain.events.production_order_events import (
    ProductionOrderStatusChanged,
)
from src.modules.fulfillment.domain.events.quote_request_events import QuoteRequestStatusChanged
from src.modules.fulfillment.domain.events.source_item_demand_events import (
    SourceItemDemandStatusChanged,
)
from src.modules.fulfillment.domain.services.lifecycle.snapshot import LifecycleSnapshot
from src.modules.fulfillment.domain.services.lifecycle.stored import FieldChange
from src.modules.fulfillment.domain.services.lifecycle.stored import LifecycleField
from src.modules.fulfillment.domain.services.lot_event_service import build_lot_event
from src.modules.fulfillment.domain.value_objects.lifecycle_aggregate import LifecycleAggregate
from src.modules.fulfillment.domain.value_objects.lot_event_type import LotEventType
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionStatus
from src.modules.fulfillment.domain.value_objects.lot_status import LotStatus
from src.modules.fulfillment.domain.value_objects.order_status import OrderItemStatus
from src.modules.fulfillment.domain.value_objects.order_status import OrderStatus
from src.modules.fulfillment.domain.value_objects.production_status import ProductionOrderStatus
from src.modules.fulfillment.domain.value_objects.quote_request_status import QuoteRequestStatus
from src.modules.fulfillment.domain.value_objects.source_item_demand_status import (
    SourceItemDemandStatus,
)
from src.modules.platform.domain.entities.user import User
from src.shared_kernel.domain.events.base import DomainEvent


@dataclass(frozen=True)
class LifecycleEffects:
    """What the changes publish, in change order."""

    events: tuple[DomainEvent, ...] = ()
    lot_events: tuple[LotEvent, ...] = ()


@dataclass(frozen=True)
class _Context:
    snapshot: LifecycleSnapshot
    actor: User
    touched_order_items: frozenset[int]
    positions: Mapping[int, LotPosition]


_NONE = LifecycleEffects()


def _member[E: Enum](enum: type[E], value: str) -> E | None:
    """The member with the value, None for a value that names none (a stored
    status no writer of the enum produced)."""
    try:
        return enum(value)
    except ValueError:
        return None


# A lot leaves ON_HOLD for one of these only when its resume clears the hold.
_RESUMED_TO = frozenset(
    {
        LotStatus.DRAFT,
        LotStatus.PARTIALLY_PLANNED,
        LotStatus.PLANNED,
        LotStatus.IN_PROGRESS,
    }
)


def _lot_timeline_row(
    lot: ProductionLot, old: LotStatus | None, new: LotStatus, actor: User
) -> LotEvent | None:
    """The timeline row of a lot status change, None when the intent that
    caused it writes its own (module docstring)."""
    if new is LotStatus.COMPLETED:
        if lot.force_completed_at is not None:
            return None
        return build_lot_event(lot.id, actor, LotEventType.LOT_COMPLETED, "lot", "Lot completed.")
    if new is LotStatus.SCRAPPED:
        return build_lot_event(
            lot.id,
            actor,
            LotEventType.LOT_SCRAPPED,
            "lot",
            "Lot scrapped, nothing left to produce.",
        )
    if old is None or new in (LotStatus.CANCELED, LotStatus.ON_HOLD):
        return None
    if old is LotStatus.ON_HOLD and new in _RESUMED_TO:
        return None
    return build_lot_event(
        lot.id,
        actor,
        LotEventType.LOT_STATUS_CHANGED,
        "lot",
        f"Status: {old.value} → {new.value}.",
        payload={"old_status": old.value, "new_status": new.value},
    )


def _lot(change: FieldChange, ctx: _Context) -> LifecycleEffects:
    lot = ctx.snapshot.lots.get(change.id)
    old = _member(LotStatus, change.old)
    new = _member(LotStatus, change.new)
    if lot is None or new is None:
        return _NONE
    events: list[DomainEvent] = []
    if old is not None:
        events.append(
            LotStatusChanged(
                lot_id=lot.id,
                lot_number=lot.lot_number,
                creator_id=lot.creator_id,
                old_status=old,
                new_status=new,
                actor_id=ctx.actor.id,
            )
        )
    if new is LotStatus.COMPLETED:
        events.append(
            LotCompleted(
                lot_id=lot.id,
                lot_number=lot.lot_number,
                creator_id=lot.creator_id,
                made_item_id=lot.made_item_id,
            )
        )
    row = _lot_timeline_row(lot, old, new, ctx.actor)
    return LifecycleEffects(events=tuple(events), lot_events=(row,) if row is not None else ())


def _position(change: FieldChange, ctx: _Context) -> LifecycleEffects:
    position = ctx.positions.get(change.id)
    old = _member(LotPositionStatus, change.old)
    new = _member(LotPositionStatus, change.new)
    if position is None or old is None or new is None:
        return _NONE
    event = LotPositionStatusChanged(
        lot_id=position.lot_id,
        position_id=position.id,
        old_status=old,
        new_status=new,
        actor_id=ctx.actor.id,
    )
    return LifecycleEffects(events=(event,))


def _production_order(change: FieldChange, ctx: _Context) -> LifecycleEffects:
    order = ctx.snapshot.production_orders.get(change.id)
    new = _member(ProductionOrderStatus, change.new)
    if order is None or new is None:
        return _NONE
    events: list[DomainEvent] = []
    old = _member(ProductionOrderStatus, change.old)
    if old is not None:
        events.append(
            ProductionOrderStatusChanged(
                production_order_id=order.id,
                old_status=old,
                new_status=new,
                actor_id=ctx.actor.id,
                creator_id=order.creator_id,
            )
        )
    if new is ProductionOrderStatus.COMPLETED:
        events.append(
            ProductionOrderCompleted(
                production_order_id=order.id,
                machine_id=order.machine_id,
                creator_id=order.creator_id,
            )
        )
    elif new is ProductionOrderStatus.CANCELED:
        events.append(
            ProductionOrderCanceled(
                production_order_id=order.id, actor_id=ctx.actor.id, creator_id=order.creator_id
            )
        )
    return LifecycleEffects(events=tuple(events))


def _order_item(change: FieldChange, ctx: _Context) -> LifecycleEffects:
    item = ctx.snapshot.order_items.get(change.id)
    old = _member(OrderItemStatus, change.old)
    new = _member(OrderItemStatus, change.new)
    if item is None or old is None or new is None:
        return _NONE
    event = OrderItemStatusChanged(
        order_item_id=item.id,
        order_id=item.order_id,
        line_type=item.line_type,
        lot_position_id=item.lot_position_id,
        old_status=old,
        new_status=new,
        actor_id=ctx.actor.id,
    )
    return LifecycleEffects(events=(event,))


def _order(change: FieldChange, ctx: _Context) -> LifecycleEffects:
    order = ctx.snapshot.orders.get(change.id)
    old = _member(OrderStatus, change.old)
    new = _member(OrderStatus, change.new)
    if order is None or old is None or new is None:
        return _NONE
    event = OrderStatusChanged(
        order_id=order.id,
        order_number=order.order_number,
        supplier_id=order.supplier_id,
        creator_id=order.creator_id,
        old_status=old,
        new_status=new,
        actor_id=ctx.actor.id,
    )
    return LifecycleEffects(events=(event,))


def _delivering_line(ctx: _Context, demand_id: int) -> int | None:
    lines = [
        a.order_item_id
        for a in ctx.snapshot.bought_allocations
        if a.demand_item_id == demand_id
        and a.order_item_id is not None
        and a.order_item_id in ctx.touched_order_items
        and a.order_item_id in ctx.snapshot.order_items
    ]
    return max(lines) if lines else None


def _bought_demand(change: FieldChange, ctx: _Context) -> LifecycleEffects:
    demand = ctx.snapshot.bought_demands.get(change.id)
    old = _member(BoughtItemDemandStatus, change.old)
    new = _member(BoughtItemDemandStatus, change.new)
    if demand is None or old is None or new is None:
        return _NONE
    line_id = _delivering_line(ctx, demand.id) if new is BoughtItemDemandStatus.FULFILLED else None
    event = DemandItemStatusChanged(
        demand_id=demand.id,
        item_article_name=demand.item_article_name,
        old_status=old,
        new_status=new,
        actor_id=ctx.actor.id,
        notify_on_delivery=demand.notify_on_delivery,
        creator_id=demand.creator_id,
        order_id=ctx.snapshot.order_items[line_id].order_id if line_id is not None else None,
        order_item_id=line_id,
    )
    return LifecycleEffects(events=(event,))


def _made_demand(change: FieldChange, ctx: _Context) -> LifecycleEffects:
    demand = ctx.snapshot.made_demands.get(change.id)
    old = _member(MadeItemDemandStatus, change.old)
    new = _member(MadeItemDemandStatus, change.new)
    if demand is None or old is None or new is None:
        return _NONE
    event = MadeItemDemandItemStatusChanged(
        demand_id=demand.id,
        item_article_name=demand.item_article_name,
        old_status=old,
        new_status=new,
        actor_id=ctx.actor.id,
        notify_on_delivery=demand.notify_on_delivery,
        creator_id=demand.creator_id,
    )
    return LifecycleEffects(events=(event,))


def _material_name(demand: SourceItemDemandItem) -> str:
    """The raw material a source demand asks for, named as the lot detail
    names it."""
    if demand.bought_item is not None:
        return demand.bought_item.article_name
    if demand.source_item is not None:
        return demand.source_item.dimension or f"Source item #{demand.source_item.id}"
    return f"Source item demand #{demand.id}"


def _source_demand(change: FieldChange, ctx: _Context) -> LifecycleEffects:
    demand = ctx.snapshot.source_demands.get(change.id)
    old = _member(SourceItemDemandStatus, change.old)
    new = _member(SourceItemDemandStatus, change.new)
    if demand is None or old is None or new is None:
        return _NONE
    event = SourceItemDemandStatusChanged(
        demand_id=demand.id,
        lot_id=demand.lot_id,
        material_name=_material_name(demand),
        old_status=old,
        new_status=new,
        actor_id=ctx.actor.id,
        notify_on_delivery=demand.notify_on_delivery,
        creator_id=demand.creator_id,
    )
    return LifecycleEffects(events=(event,))


def _quote_request(change: FieldChange, ctx: _Context) -> LifecycleEffects:
    request = ctx.snapshot.quote_requests.get(change.id)
    old = _member(QuoteRequestStatus, change.old)
    new = _member(QuoteRequestStatus, change.new)
    if request is None or old is None or new is None:
        return _NONE
    event = QuoteRequestStatusChanged(
        quote_request_id=request.id,
        request_number=request.request_number,
        creator_id=request.creator_id,
        old_status=old,
        new_status=new,
        actor_id=ctx.actor.id,
    )
    return LifecycleEffects(events=(event,))


_ON_STATUS_CHANGE: dict[LifecycleAggregate, Callable[[FieldChange, _Context], LifecycleEffects]] = {
    LifecycleAggregate.LOTS: _lot,
    LifecycleAggregate.LOT_POSITIONS: _position,
    LifecycleAggregate.PRODUCTION_ORDERS: _production_order,
    LifecycleAggregate.ORDER_ITEMS: _order_item,
    LifecycleAggregate.ORDERS: _order,
    LifecycleAggregate.BOUGHT_DEMANDS: _bought_demand,
    LifecycleAggregate.MADE_DEMANDS: _made_demand,
    LifecycleAggregate.SOURCE_DEMANDS: _source_demand,
    LifecycleAggregate.QUOTE_REQUESTS: _quote_request,
}


def lifecycle_effects(
    changes: Iterable[FieldChange],
    snapshot: LifecycleSnapshot,
    actor: User,
    *,
    touched_order_items: frozenset[int] = frozenset(),
) -> LifecycleEffects:
    """The events and timeline rows of the status changes, see the module
    docstring. Changes of other fields publish nothing."""
    ctx = _Context(
        snapshot=snapshot,
        actor=actor,
        touched_order_items=touched_order_items,
        positions=snapshot.positions(),
    )
    events: list[DomainEvent] = []
    lot_events: list[LotEvent] = []
    for change in changes:
        handler = _ON_STATUS_CHANGE.get(change.aggregate)
        if change.field is not LifecycleField.STATUS or handler is None:
            continue
        effects = handler(change, ctx)
        events.extend(effects.events)
        lot_events.extend(effects.lot_events)
    return LifecycleEffects(events=tuple(events), lot_events=tuple(lot_events))
