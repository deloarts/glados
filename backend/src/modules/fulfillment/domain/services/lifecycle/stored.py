"""The stored lifecycle fields of an entity next to their derivation: which of
them differ, and writing the derived values back.

Every aggregate stores its derived status. A lot position also stores its
derived kind and completed count, a production order the pieces its
completion rows accepted, and three aggregates store a stamp of their
status: a lot's completed_at while it is COMPLETED, a production order's
actual_end while it is COMPLETED and an order's delivery_date while it is
DELIVERED. A stamp is set when its status is entered and cleared when the
derived status leaves it, so it never contradicts the status. An order's
ordered_date is recorded the first time the order derives ORDERED without it
and never cleared (_ordered_date_change says why).

A production order that becomes COMPLETED or CANCELED also drops its planned
window, since it no longer occupies its machine; a walk plans it again if it
is revived.

A stamp is dated at the moment the run finds it missing, which is the moment
its status is entered, because the reconciler sets the stamp together with
the status.

The completed counts are stored capped at the position's or the order's
quantity, because a database constraint holds each there; a count above the quantity is a fact
anomaly, which completed_over_quantity tells the drift report about.

The `*_changes` functions compare and change nothing; they return one
FieldChange per differing field, so the drift report and the reconciler judge
a row the same way. The `apply_*` functions write the changes onto the entity
they were computed for, and they are the only code that assigns a lifecycle
status or kind (tests/unit/test_architecture.py checks it), so every stored
status comes from a derivation.
"""

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from enum import unique
from typing import Protocol

from src.modules.catalogue.domain.value_objects.bought_item_status import BoughtItemDemandStatus
from src.modules.catalogue.domain.value_objects.made_item_status import MadeItemDemandStatus
from src.modules.fulfillment.domain.entities.lot_position import LotPosition
from src.modules.fulfillment.domain.entities.order import Order
from src.modules.fulfillment.domain.entities.order_item import OrderItem
from src.modules.fulfillment.domain.entities.production_lot import ProductionLot
from src.modules.fulfillment.domain.entities.production_order import ProductionOrder
from src.modules.fulfillment.domain.entities.quote_request import QuoteRequest
from src.modules.fulfillment.domain.entities.source_item_demand_item import SourceItemDemandItem
from src.modules.fulfillment.domain.services.lifecycle.facts import DemandFacts
from src.modules.fulfillment.domain.services.lifecycle.facts import OrderFacts
from src.modules.fulfillment.domain.services.lifecycle.facts import OrderItemFacts
from src.modules.fulfillment.domain.services.lifecycle.facts import ProductionOrderFacts
from src.modules.fulfillment.domain.services.lifecycle.quote_request import QuoteRequestFacts
from src.modules.fulfillment.domain.services.lifecycle.snapshot import Derived
from src.modules.fulfillment.domain.services.lifecycle.snapshot import DerivedLot
from src.modules.fulfillment.domain.services.lifecycle.snapshot import DerivedPosition
from src.modules.fulfillment.domain.services.lifecycle.snapshot import accepted_pieces
from src.modules.fulfillment.domain.value_objects.lifecycle_aggregate import LifecycleAggregate
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionKind
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionStatus
from src.modules.fulfillment.domain.value_objects.lot_status import LotStatus
from src.modules.fulfillment.domain.value_objects.order_status import OrderItemStatus
from src.modules.fulfillment.domain.value_objects.order_status import OrderStatus
from src.modules.fulfillment.domain.value_objects.production_status import (
    TERMINAL_PRODUCTION_ORDER_STATUSES,
)
from src.modules.fulfillment.domain.value_objects.production_status import ProductionOrderStatus
from src.modules.fulfillment.domain.value_objects.quote_request_status import QuoteRequestStatus
from src.modules.fulfillment.domain.value_objects.source_item_demand_status import (
    SourceItemDemandStatus,
)
from src.modules.platform.domain.services.quantities import quantity_eq
from src.modules.platform.domain.services.quantities import quantity_gt
from src.shared_kernel.domain.value_objects.value_enum import StrValueEnum


@unique
class LifecycleField(str, Enum):
    """A stored field the lifecycle derivation decides."""

    STATUS = "status"
    KIND = "kind"
    QUANTITY_COMPLETED = "quantity_completed"
    COMPLETED_AT = "completed_at"
    ACTUAL_END = "actual_end"
    DELIVERY_DATE = "delivery_date"
    ORDERED_DATE = "ordered_date"


_LABELS = {
    LifecycleField.STATUS: "Status",
    LifecycleField.KIND: "Kind",
    LifecycleField.QUANTITY_COMPLETED: "Completed quantity",
    LifecycleField.COMPLETED_AT: "Completed at",
    LifecycleField.ACTUAL_END: "Actual end",
    LifecycleField.DELIVERY_DATE: "Delivery date",
    LifecycleField.ORDERED_DATE: "Ordered date",
}
_STAMPS = frozenset(
    {
        LifecycleField.COMPLETED_AT,
        LifecycleField.ACTUAL_END,
        LifecycleField.DELIVERY_DATE,
        LifecycleField.ORDERED_DATE,
    }
)

COMPLETED_COUNT_RULE = (
    "the live line's delivered pieces plus the pieces the position's production orders "
    "completed, capped at the position quantity"
)
ORDER_COMPLETED_COUNT_RULE = (
    "the accepted pieces of the order's completion rows, reversals netted out, "
    "capped at the order quantity"
)
COMPLETED_OVER_QUANTITY_RULE = (
    "fact anomaly: the live line's delivered pieces plus the pieces the position's "
    "production orders completed exceed the position quantity"
)
type StoredValue = str | float | datetime | None


@dataclass(frozen=True)
class FieldChange:
    """One stored field that differs from its derivation. `old` and `new`
    are display texts; `value` is what the field gets."""

    aggregate: LifecycleAggregate
    id: int
    field: LifecycleField
    old: str
    new: str
    rule: str
    value: StoredValue

    def note(self, reason: str) -> str:
        """The changelog text, such as `Status: ordered → delivered (reason).`"""
        label = _LABELS[self.field]
        if self.field in _STAMPS:
            return f"{label}: {'set' if self.value is not None else 'cleared'} ({reason})."
        return f"{label}: {self.old} → {self.new} ({reason})."


def _moment_text(value: datetime | None) -> str:
    return value.isoformat(timespec="seconds") if value is not None else "-"


def _status_change[V: Enum, F](
    aggregate: LifecycleAggregate, row_id: int, stored: StrValueEnum, derived: Derived[V, F]
) -> list[FieldChange]:
    new = str(derived.value.value)
    if stored == new:
        return []
    return [
        FieldChange(
            aggregate=aggregate,
            id=row_id,
            field=LifecycleField.STATUS,
            old=stored.value,
            new=new,
            rule=str(derived.rule),
            value=new,
        )
    ]


def _stamp_change(
    aggregate: LifecycleAggregate,
    row_id: int,
    field: LifecycleField,
    stored: datetime | None,
    *,
    entered: bool,
    now: datetime,
    status: str,
) -> list[FieldChange]:
    """`now` is the moment the stamp gets when it is missing."""
    rule = f"{field.value} is set exactly while the status is {status}"
    if entered and stored is None:
        return [FieldChange(aggregate, row_id, field, "-", "set", rule, now)]
    if not entered and stored is not None:
        return [FieldChange(aggregate, row_id, field, _moment_text(stored), "-", rule, None)]
    return []


# ── Comparisons ──────────────────────────────────────────────────────


def order_item_changes(
    item: OrderItem, derived: Derived[OrderItemStatus, OrderItemFacts]
) -> list[FieldChange]:
    return _status_change(LifecycleAggregate.ORDER_ITEMS, item.id, item.status, derived)


def production_order_changes(
    order: ProductionOrder,
    derived: Derived[ProductionOrderStatus, ProductionOrderFacts],
    *,
    now: datetime,
) -> list[FieldChange]:
    aggregate = LifecycleAggregate.PRODUCTION_ORDERS
    completed = ProductionOrderStatus.COMPLETED.value
    changes = _status_change(aggregate, order.id, order.status, derived) + _stamp_change(
        aggregate,
        order.id,
        LifecycleField.ACTUAL_END,
        order.actual_end,
        entered=derived.value.value == completed,
        now=now,
        status=completed,
    )
    count = stored_order_completed_count(order)
    if not quantity_eq(order.quantity_completed, count):
        changes.append(
            FieldChange(
                aggregate,
                order.id,
                LifecycleField.QUANTITY_COMPLETED,
                f"{order.quantity_completed:g}",
                f"{count:g}",
                ORDER_COMPLETED_COUNT_RULE,
                count,
            )
        )
    return changes


def stored_order_completed_count(order: ProductionOrder) -> float:
    """The completed count to store on a production order: the accepted
    pieces of its completion rows, never above the order quantity."""
    return min(accepted_pieces(order), order.quantity)


def stored_completed_count(position: LotPosition, derived: DerivedPosition) -> float:
    """The completed count to store: the derived count, never above the
    position quantity."""
    return min(derived.quantity_completed, position.quantity)


def completed_over_quantity(position: LotPosition, derived: DerivedPosition) -> bool:
    """True when the facts give the position more completed pieces than its
    quantity, beyond the tolerance."""
    return quantity_gt(derived.quantity_completed, position.quantity)


def position_changes(position: LotPosition, derived: DerivedPosition) -> list[FieldChange]:
    aggregate = LifecycleAggregate.LOT_POSITIONS
    changes: list[FieldChange] = []
    kind = str(derived.kind.value.value)
    if position.kind != kind:
        changes.append(
            FieldChange(
                aggregate,
                position.id,
                LifecycleField.KIND,
                position.kind.value,
                kind,
                str(derived.kind.rule),
                kind,
            )
        )
    changes += _status_change(aggregate, position.id, position.status, derived.status)
    count = stored_completed_count(position, derived)
    if not quantity_eq(position.quantity_completed, count):
        changes.append(
            FieldChange(
                aggregate,
                position.id,
                LifecycleField.QUANTITY_COMPLETED,
                f"{position.quantity_completed:g}",
                f"{count:g}",
                COMPLETED_COUNT_RULE,
                count,
            )
        )
    return changes


def lot_changes(lot: ProductionLot, derived: DerivedLot, *, now: datetime) -> list[FieldChange]:
    aggregate = LifecycleAggregate.LOTS
    completed = LotStatus.COMPLETED.value
    return _status_change(aggregate, lot.id, lot.status, derived.status) + _stamp_change(
        aggregate,
        lot.id,
        LifecycleField.COMPLETED_AT,
        lot.completed_at,
        entered=derived.status.value.value == completed,
        now=now,
        status=completed,
    )


def order_changes(
    order: Order, derived: Derived[OrderStatus, OrderFacts], *, now: datetime
) -> list[FieldChange]:
    aggregate = LifecycleAggregate.ORDERS
    delivered = OrderStatus.DELIVERED.value
    return (
        _status_change(aggregate, order.id, order.status, derived)
        + _ordered_date_change(order, derived, now=now)
        + _stamp_change(
            aggregate,
            order.id,
            LifecycleField.DELIVERY_DATE,
            order.delivery_date,
            entered=derived.value.value == delivered,
            now=now,
            status=delivered,
        )
    )


def _ordered_date_change(
    order: Order, derived: Derived[OrderStatus, OrderFacts], *, now: datetime
) -> list[FieldChange]:
    """ordered_date is the order's placed intent, which submitting the order
    records. An order whose lines were all marked ordered one by one is
    placed as well and derives ORDERED from its lines, so the first time it
    does so without the date, the date is recorded: the order list sorts and
    filters by it. Recording it changes no status, since the order already
    derives ORDERED. The date is never cleared, because a placed order stays
    placed whatever its lines do later: with the date, the derivation keeps
    the order ORDERED when a pending line is added, as for an order that was
    submitted."""
    if derived.value is not OrderStatus.ORDERED or order.ordered_date is not None:
        return []
    return [
        FieldChange(
            LifecycleAggregate.ORDERS,
            order.id,
            LifecycleField.ORDERED_DATE,
            "-",
            "set",
            "ordered_date is recorded the first time the order is ORDERED",
            now,
        )
    ]


class _Demand(Protocol):
    @property
    def id(self) -> int: ...

    @property
    def status(self) -> StrValueEnum: ...


def demand_changes[S: (BoughtItemDemandStatus, MadeItemDemandStatus)](
    aggregate: LifecycleAggregate, demand: _Demand, derived: Derived[S, DemandFacts]
) -> list[FieldChange]:
    """The status change of a bought or made demand; a source demand goes
    through source_demand_changes."""
    return _status_change(aggregate, demand.id, demand.status, derived)


def source_demand_changes(
    demand: SourceItemDemandItem, derived: Derived[SourceItemDemandStatus, DemandFacts]
) -> list[FieldChange]:
    return _status_change(LifecycleAggregate.SOURCE_DEMANDS, demand.id, demand.status, derived)


def quote_request_changes(
    request: QuoteRequest, derived: Derived[QuoteRequestStatus, QuoteRequestFacts]
) -> list[FieldChange]:
    return _status_change(LifecycleAggregate.QUOTE_REQUESTS, request.id, request.status, derived)


# ── Writes ───────────────────────────────────────────────────────────


def _text(change: FieldChange) -> str:
    if not isinstance(change.value, str):
        raise TypeError(f"{change.field.value} needs a text value, got {change.value!r}.")
    return change.value


def _moment(change: FieldChange) -> datetime | None:
    if change.value is not None and not isinstance(change.value, datetime):
        raise TypeError(f"{change.field.value} needs a datetime or None, got {change.value!r}.")
    return change.value


def _count(change: FieldChange) -> float:
    if isinstance(change.value, bool) or not isinstance(change.value, int | float):
        raise TypeError(f"{change.field.value} needs a number, got {change.value!r}.")
    return float(change.value)


def _unexpected(change: FieldChange) -> ValueError:
    return ValueError(f"{change.aggregate.value} store no {change.field.value}.")


def apply_order_item_changes(item: OrderItem, changes: Iterable[FieldChange]) -> None:
    for change in changes:
        if change.field is not LifecycleField.STATUS:
            raise _unexpected(change)
        item.status = OrderItemStatus(_text(change))


def apply_production_order_changes(order: ProductionOrder, changes: Iterable[FieldChange]) -> None:
    for change in changes:
        if change.field is LifecycleField.STATUS:
            order.status = ProductionOrderStatus(_text(change))
            if order.status in TERMINAL_PRODUCTION_ORDER_STATUSES:
                # A completed or canceled order no longer holds its machine,
                # so its planned window would overlap the next order there;
                # its actual window and planned_end_at_start remain.
                order.planned_start = None
                order.planned_end = None
                order.planned_by_id = None
        elif change.field is LifecycleField.ACTUAL_END:
            order.actual_end = _moment(change)
        elif change.field is LifecycleField.QUANTITY_COMPLETED:
            order.quantity_completed = _count(change)
        else:
            raise _unexpected(change)


def apply_position_changes(position: LotPosition, changes: Iterable[FieldChange]) -> None:
    for change in changes:
        if change.field is LifecycleField.STATUS:
            position.status = LotPositionStatus(_text(change))
        elif change.field is LifecycleField.KIND:
            position.kind = LotPositionKind(_text(change))
        elif change.field is LifecycleField.QUANTITY_COMPLETED:
            position.quantity_completed = _count(change)
        else:
            raise _unexpected(change)


def apply_lot_changes(lot: ProductionLot, changes: Iterable[FieldChange]) -> None:
    for change in changes:
        if change.field is LifecycleField.STATUS:
            lot.status = LotStatus(_text(change))
        elif change.field is LifecycleField.COMPLETED_AT:
            lot.completed_at = _moment(change)
        else:
            raise _unexpected(change)


def apply_order_changes(order: Order, changes: Iterable[FieldChange]) -> None:
    for change in changes:
        if change.field is LifecycleField.STATUS:
            order.status = OrderStatus(_text(change))
        elif change.field is LifecycleField.DELIVERY_DATE:
            order.delivery_date = _moment(change)
        elif change.field is LifecycleField.ORDERED_DATE:
            order.ordered_date = _moment(change)
        else:
            raise _unexpected(change)


class _MutableDemand[S: (BoughtItemDemandStatus, MadeItemDemandStatus)](Protocol):
    status: S


def apply_demand_changes[S: (BoughtItemDemandStatus, MadeItemDemandStatus)](
    demand: _MutableDemand[S], changes: Iterable[FieldChange]
) -> None:
    """The status is parsed with the enum of the demand's own family."""
    for change in changes:
        if change.field is not LifecycleField.STATUS:
            raise _unexpected(change)
        demand.status = type(demand.status)(_text(change))


def apply_quote_request_changes(request: QuoteRequest, changes: Iterable[FieldChange]) -> None:
    for change in changes:
        if change.field is not LifecycleField.STATUS:
            raise _unexpected(change)
        request.status = QuoteRequestStatus(_text(change))


def apply_source_demand_changes(
    demand: SourceItemDemandItem, changes: Iterable[FieldChange]
) -> None:
    for change in changes:
        if change.field is not LifecycleField.STATUS:
            raise _unexpected(change)
        demand.status = SourceItemDemandStatus(_text(change))
