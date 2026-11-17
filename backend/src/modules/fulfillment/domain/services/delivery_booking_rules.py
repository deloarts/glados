"""Business rules for booking a delivery on an order line. No I/O.

They decide which pieces a booking accepts, what it writes on the line, when
it refits the line's allocations or closes the line short, and whether the
pieces of a MADE line fit its lot. Deliver-all uses the same rules to pick the
lines it locks and to name why it left a line alone. Whether a line may take a
delivery at all is OrderRules.can_deliver; the use cases in
application/use_cases/order read and write the rows around these rules.
"""

import copy
from collections.abc import Iterable
from datetime import datetime
from typing import Literal

from src.modules.catalogue.domain.value_objects.bought_item_status import BoughtItemDemandStatus
from src.modules.fulfillment.domain.entities.lot_position import LotPosition
from src.modules.fulfillment.domain.entities.order import Order
from src.modules.fulfillment.domain.entities.order_item import OrderItem
from src.modules.fulfillment.domain.entities.production_lot import ProductionLot
from src.modules.fulfillment.domain.services.delivery_tolerance import DeliveryTolerance
from src.modules.fulfillment.domain.services.delivery_tolerance import closes_within_under_tolerance
from src.modules.fulfillment.domain.services.lifecycle.stored import FieldChange
from src.modules.fulfillment.domain.services.lifecycle.stored import LifecycleField
from src.modules.fulfillment.domain.services.lot_rules import assert_completion_within_available
from src.modules.fulfillment.domain.services.lot_rules import assert_delivery_disposition_allowed
from src.modules.fulfillment.domain.services.lot_rules import assert_disposition_keeps_completed
from src.modules.fulfillment.domain.value_objects.lifecycle_aggregate import LifecycleAggregate
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionKind
from src.modules.fulfillment.domain.value_objects.order_status import OrderItemStatus
from src.modules.fulfillment.domain.value_objects.order_status import OrderLineType
from src.modules.fulfillment.domain.value_objects.order_status import OrderStatus
from src.modules.fulfillment.domain.value_objects.rejection_after_receipt import (
    RejectionAfterReceipt,
)
from src.modules.fulfillment.domain.value_objects.rejection_outcome import RejectionOutcome
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.services.quantities import quantity_gt
from src.shared_kernel.domain.services.changelog_service import append_changelog

type DeliverAllSkipReason = Literal[
    "not_ordered", "delivered", "canceled", "order_canceled", "lot_canceled"
]

# The line statuses deliver-all books a delivery on.
OPEN_FOR_DELIVERY = frozenset({OrderItemStatus.ORDERED, OrderItemStatus.PARTIALLY_DELIVERED})


def loses_made_pieces(line: OrderItem, quantity_rejected: float, outcome: str | None) -> bool:
    """Whether a booking on the line loses pieces of a lot, whose
    disposition may cut the lot's other work."""
    return (
        line.line_type == OrderLineType.MADE
        and quantity_rejected > 0
        and outcome == RejectionOutcome.LOST
    )


def supplying_position_id(line: OrderItem) -> int | None:
    """The lot position a MADE line takes its pieces from, None for any other
    line and for a MADE line without a position."""
    if line.line_type != OrderLineType.MADE:
        return None
    return line.lot_position_id


def remaining_to_deliver(line: OrderItem) -> float:
    """The pieces the line still waits for. Lost pieces are settled, while
    pieces sent back for redelivery stay open."""
    return line.quantity - line.quantity_delivered - line.quantity_rejected_lost


def accepted_quantity(remaining: float, quantity: float | None, quantity_rejected: float) -> float:
    """The pieces a booking accepts: `quantity` when it names one, else
    everything left after the rejected pieces."""
    return (remaining - quantity_rejected) if quantity is None else quantity


def booked_storage_place(storage_place: str | None, line: OrderItem) -> str | None:
    """A booking without a storage place keeps the line's, since the goods
    went where the earlier ones did, and the delivery row records that place
    too."""
    return (storage_place or "").strip() or line.storage_place


def record_delivery_on_line(
    line: OrderItem,
    actor: User,
    now: datetime,
    *,
    delivered_now: float,
    quantity_rejected: float,
    rejection_reason: str | None,
    rejection_outcome: str | None,
    storage_place: str | None,
) -> None:
    """Adds a booking to the line's totals, receipt fields and changelog.
    Lost pieces count as settled, and pieces sent back for redelivery clear
    the expected delivery date so the user asks the supplier for a fresh one.
    The line's status follows when the lifecycle reconciler runs."""
    line.quantity_delivered += delivered_now
    line.quantity_rejected += quantity_rejected
    if rejection_outcome == RejectionOutcome.LOST:
        line.quantity_rejected_lost += quantity_rejected
    elif rejection_outcome == RejectionOutcome.REDELIVER:
        line.expected_delivery_date = None
    line.delivery_date = now
    line.storage_place = storage_place
    line.receiver_id = actor.id
    line.receiver = actor
    line.changed = now
    changelog_message = (
        f"Delivered {delivered_now:.3f} {line.unit} on {now:%Y-%m-%d} "
        f"({line.quantity_delivered:.3f}/{line.quantity:.3f} total)."
        + (f" Storage: {storage_place}." if storage_place else "")
    )
    if quantity_rejected > 0:
        changelog_message += (
            f" Rejected {quantity_rejected:.3f} {line.unit} ({rejection_reason}, "
            f"{rejection_outcome})."
        )
    line.changes = append_changelog(line.changes, actor.full_name, changelog_message)


def record_rejection_after_receipt(
    line: OrderItem,
    actor: User,
    now: datetime,
    *,
    delivery_id: int,
    quantity: float,
    rejection: RejectionAfterReceipt,
) -> None:
    """Takes `quantity` accepted pieces of delivery row `delivery_id` back as
    rejected ones in the line's totals and changelog, as a rejection at
    receipt would have booked them: lost pieces count as settled, and pieces
    sent back for redelivery clear the expected delivery date so the user
    asks the supplier for a fresh one. The caller derives the line's delivery
    date from its rows, and the line's status follows when the lifecycle
    reconciler runs."""
    line.quantity_delivered -= quantity
    line.quantity_rejected += quantity
    if rejection.outcome == RejectionOutcome.LOST:
        line.quantity_rejected_lost += quantity
    elif rejection.outcome == RejectionOutcome.REDELIVER:
        line.expected_delivery_date = None
    line.changed = now
    line.changes = append_changelog(
        line.changes,
        actor.full_name,
        f"Delivery #{delivery_id}: rejected {quantity:.3f} {line.unit} after receipt "
        f"({rejection.reason}, {rejection.outcome.value}); "
        f"{line.quantity_delivered:.3f}/{line.quantity:.3f} delivered.",
    )


def refits_lost_allocations(line: OrderItem, rejection_outcome: str | None) -> bool:
    """Whether a booking refits the line's allocations to what can still
    arrive: pieces lost at receipt on a bought or source line never arrive
    and the supplier sends nothing for them. A MADE line's lost pieces go
    through the lot's disposition instead."""
    return rejection_outcome == RejectionOutcome.LOST and line.line_type != OrderLineType.MADE


def closes_short_on_booking(
    line: OrderItem, tolerance: DeliveryTolerance, rejection_outcome: str | None
) -> bool:
    """Whether the booked line closes short, because what it still lacks is
    within its under-delivery tolerance. A booking that sends pieces back for
    redelivery leaves the line open, since more is coming."""
    return rejection_outcome != RejectionOutcome.REDELIVER and (
        closes_within_under_tolerance(line, tolerance)
    )


def draws_on_raw_material(lot: ProductionLot, position: LotPosition) -> bool:
    """Whether a delivery on the position consumes the lot's raw material: a
    MIXED position 1 draws on ours, a pure EXTERNAL supplier sources its own,
    and an alteration lot has none."""
    return (
        position.sequence == 1 and position.kind == LotPositionKind.MIXED and not lot.is_alteration
    )


def assert_made_booking_fits(
    line: OrderItem,
    lot: ProductionLot,
    position: LotPosition,
    *,
    delivered_now: float,
    quantity_rejected: float,
    rejection_outcome: str | None,
    accepted_earlier: dict[int, float] | None,
    raw_material_arrived: float | None,
) -> None:
    """Checks a booking on a MADE line against its lot: the accepted pieces
    must fit what the position's upstream made available, and lost pieces
    must be ones the lot can dispose of. `accepted_earlier` maps a position
    to the pieces bookings earlier in the same transaction accepted on it,
    which count as completed here. `raw_material_arrived` is what the lot's
    input demand received, for a position that draws on raw material."""
    positions = _with_accepted(lot.positions, accepted_earlier)
    checked = next(p for p in positions if p.id == position.id)
    if quantity_gt(delivered_now, 0.0):
        assert_completion_within_available(
            checked, positions, lot.quantity, delivered_now, raw_material_arrived
        )
    if loses_made_pieces(line, quantity_rejected, rejection_outcome):
        assert_delivery_disposition_allowed(lot, position)
        assert_disposition_keeps_completed(
            _lot_view(lot, positions), checked, quantity_rejected, accepted_now=delivered_now
        )


def fulfilled_bought_demands(changes: Iterable[FieldChange]) -> int:
    """How many bought demands a reconciler run set to fulfilled."""
    return sum(
        1
        for c in changes
        if c.aggregate is LifecycleAggregate.BOUGHT_DEMANDS
        and c.field is LifecycleField.STATUS
        and c.value == BoughtItemDemandStatus.FULFILLED
    )


def is_open_for_delivery(line: OrderItem) -> bool:
    """Whether deliver-all books the line's remainder."""
    return line.status in OPEN_FOR_DELIVERY


def deliver_all_skip_reason(order: Order, line: OrderItem) -> DeliverAllSkipReason:
    """Why deliver-all left the line alone."""
    if line.canceled_at is not None or line.status == OrderItemStatus.CANCELED:
        return "canceled"
    if line.status == OrderItemStatus.DELIVERED:
        return "delivered"
    if line.status not in OPEN_FOR_DELIVERY:
        return "not_ordered"
    if order.status == OrderStatus.CANCELED:
        return "order_canceled"
    return "lot_canceled"


def _with_accepted(
    positions: list[LotPosition], accepted_earlier: dict[int, float] | None
) -> list[LotPosition]:
    """Copies of `positions` whose completed counts include the pieces
    accepted on them earlier in the transaction, never above their
    quantity; the positions themselves without any."""
    if not accepted_earlier:
        return positions
    viewed = []
    for position in positions:
        extra = accepted_earlier.get(position.id, 0.0)
        if extra:
            position = copy.copy(position)
            position.quantity_completed = min(
                position.quantity, position.quantity_completed + extra
            )
        viewed.append(position)
    return viewed


def _lot_view(lot: ProductionLot, positions: list[LotPosition]) -> ProductionLot:
    """A shallow copy of `lot` over `positions`, for checks only."""
    if positions is lot.positions:
        return lot
    view = copy.copy(lot)
    view.positions = positions
    return view
