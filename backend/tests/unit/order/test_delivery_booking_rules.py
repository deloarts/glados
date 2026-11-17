"""
The pure rules of booking a delivery on an order line: which pieces a
booking accepts and what it writes on the line, when it refits the line's
allocations or closes it short, how a MADE line's pieces are checked against
its lot, and how deliver-all picks and skips lines.
"""

import dataclasses
from datetime import UTC
from datetime import datetime

import pytest

from src.modules.fulfillment.domain.entities.lot_position import LotPosition
from src.modules.fulfillment.domain.entities.order_item import OrderItem
from src.modules.fulfillment.domain.entities.production_lot import ProductionLot
from src.modules.fulfillment.domain.errors import LotNotScrappableError
from src.modules.fulfillment.domain.errors import LotPositionOverflowError
from src.modules.fulfillment.domain.services.delivery_booking_rules import accepted_quantity
from src.modules.fulfillment.domain.services.delivery_booking_rules import assert_made_booking_fits
from src.modules.fulfillment.domain.services.delivery_booking_rules import booked_storage_place
from src.modules.fulfillment.domain.services.delivery_booking_rules import closes_short_on_booking
from src.modules.fulfillment.domain.services.delivery_booking_rules import deliver_all_skip_reason
from src.modules.fulfillment.domain.services.delivery_booking_rules import draws_on_raw_material
from src.modules.fulfillment.domain.services.delivery_booking_rules import fulfilled_bought_demands
from src.modules.fulfillment.domain.services.delivery_booking_rules import is_open_for_delivery
from src.modules.fulfillment.domain.services.delivery_booking_rules import loses_made_pieces
from src.modules.fulfillment.domain.services.delivery_booking_rules import record_delivery_on_line
from src.modules.fulfillment.domain.services.delivery_booking_rules import refits_lost_allocations
from src.modules.fulfillment.domain.services.delivery_booking_rules import remaining_to_deliver
from src.modules.fulfillment.domain.services.delivery_booking_rules import supplying_position_id
from src.modules.fulfillment.domain.services.delivery_tolerance import NO_TOLERANCE
from src.modules.fulfillment.domain.services.delivery_tolerance import DeliveryTolerance
from src.modules.fulfillment.domain.services.lifecycle.stored import FieldChange
from src.modules.fulfillment.domain.services.lifecycle.stored import LifecycleField
from src.modules.fulfillment.domain.value_objects.lifecycle_aggregate import LifecycleAggregate
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionKind
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionStatus
from src.modules.fulfillment.domain.value_objects.lot_status import LotStatus
from src.modules.fulfillment.domain.value_objects.order_status import OrderItemStatus
from src.modules.fulfillment.domain.value_objects.order_status import OrderLineType
from src.modules.fulfillment.domain.value_objects.order_status import OrderStatus
from src.modules.fulfillment.domain.value_objects.production_status import UrgencyClass
from tests.factories import make_user
from tests.unit.order._helpers import make_order
from tests.unit.order._helpers import make_order_item

_NOW = datetime(2026, 3, 2, 9, 30, tzinfo=UTC)


def _made_line(position_id: int | None = 2) -> OrderItem:
    line = make_order_item(status=OrderItemStatus.ORDERED)
    line.line_type = OrderLineType.MADE
    line.bought_item_id = None
    line.lot_position_id = position_id
    return line


def _position(id: int, sequence: int, kind: LotPositionKind, completed: float = 0.0) -> LotPosition:
    return LotPosition(
        id=id,
        created=_NOW,
        changed=None,
        changes=[],
        sequence=sequence,
        kind=kind,
        status=LotPositionStatus.IN_PROGRESS,
        quantity=10.0,
        quantity_completed=completed,
        note=None,
        creator_id=1,
        lot_id=1,
    )


def _lot(*positions: LotPosition, status: LotStatus = LotStatus.IN_PROGRESS) -> ProductionLot:
    return ProductionLot(
        id=1,
        created=_NOW,
        changed=None,
        changes=[],
        lot_number="LOT-26-00001",
        quantity=10.0,
        status=status,
        priority=UrgencyClass.NORMAL,
        note=None,
        creator_id=1,
        made_item_id=42,
        project_id=1,
        input_demand_id=None,
        positions=list(positions),
    )


def _change(aggregate: LifecycleAggregate, value: str) -> FieldChange:
    return FieldChange(
        aggregate=aggregate,
        id=1,
        field=LifecycleField.STATUS,
        old="open",
        new=value,
        rule="test",
        value=value,
    )


def test_only_lost_pieces_on_a_made_line_lose_lot_pieces() -> None:
    assert loses_made_pieces(_made_line(), 2.0, "lost")
    assert not loses_made_pieces(_made_line(), 2.0, "redeliver")
    assert not loses_made_pieces(_made_line(), 0.0, "lost")
    assert not loses_made_pieces(make_order_item(), 2.0, "lost")


def test_only_a_made_line_supplies_a_position() -> None:
    assert supplying_position_id(_made_line(7)) == 7
    assert supplying_position_id(_made_line(None)) is None
    bought = make_order_item()
    bought.lot_position_id = 7
    assert supplying_position_id(bought) is None


def test_lost_pieces_are_settled_and_redelivered_ones_stay_open() -> None:
    line = make_order_item()
    line.quantity_delivered = 4.0
    line.quantity_rejected = 3.0
    line.quantity_rejected_lost = 1.0
    assert remaining_to_deliver(line) == 5.0


def test_a_booking_without_a_quantity_accepts_the_rest_after_rejections() -> None:
    assert accepted_quantity(5.0, None, 2.0) == 3.0
    assert accepted_quantity(5.0, 4.0, 2.0) == 4.0


def test_a_booking_without_a_storage_place_keeps_the_lines() -> None:
    line = make_order_item()
    line.storage_place = "Shelf A"
    assert booked_storage_place("  ", line) == "Shelf A"
    assert booked_storage_place(None, line) == "Shelf A"
    assert booked_storage_place(" Shelf B ", line) == "Shelf B"


def test_recording_a_booking_adds_to_the_totals_and_the_changelog() -> None:
    actor = make_user(id=5, full_name="Rita Receiver")
    line = make_order_item()
    line.quantity_delivered = 2.0
    record_delivery_on_line(
        line,
        actor,
        _NOW,
        delivered_now=3.0,
        quantity_rejected=1.0,
        rejection_reason="damaged",
        rejection_outcome="lost",
        storage_place="Shelf A",
    )
    assert (line.quantity_delivered, line.quantity_rejected, line.quantity_rejected_lost) == (
        5.0,
        1.0,
        1.0,
    )
    assert line.delivery_date == _NOW
    assert line.changed == _NOW
    assert (line.storage_place, line.receiver_id, line.receiver) == ("Shelf A", 5, actor)
    assert line.changes[-1].endswith(
        ", Rita Receiver, Delivered 3.000 pcs on 2026-03-02 (5.000/10.000 total). Storage: Shelf A. "
        "Rejected 1.000 pcs (damaged, lost)."
    )


def test_a_redelivery_clears_the_expected_delivery_date_and_settles_nothing() -> None:
    line = make_order_item()
    line.expected_delivery_date = _NOW.date()
    record_delivery_on_line(
        line,
        make_user(id=5),
        _NOW,
        delivered_now=0.0,
        quantity_rejected=2.0,
        rejection_reason="wrong size",
        rejection_outcome="redeliver",
        storage_place=None,
    )
    assert line.expected_delivery_date is None
    assert line.quantity_rejected_lost == 0.0
    assert line.quantity_rejected == 2.0


def test_only_lost_pieces_on_a_supplier_line_refit_its_allocations() -> None:
    assert refits_lost_allocations(make_order_item(), "lost")
    assert not refits_lost_allocations(make_order_item(), "redeliver")
    assert not refits_lost_allocations(make_order_item(), None)
    assert not refits_lost_allocations(_made_line(), "lost")


def test_a_booking_within_the_under_tolerance_closes_short_unless_redelivered() -> None:
    line = make_order_item()
    line.quantity_delivered = 9.5
    tolerance = DeliveryTolerance(under_percent=10.0)
    assert closes_short_on_booking(line, tolerance, None)
    assert not closes_short_on_booking(line, tolerance, "redeliver")
    assert not closes_short_on_booking(line, NO_TOLERANCE, None)


def test_only_a_mixed_first_position_of_a_new_lot_draws_on_raw_material() -> None:
    mixed = _position(1, 1, LotPositionKind.MIXED)
    assert draws_on_raw_material(_lot(mixed), mixed)
    assert not draws_on_raw_material(_lot(mixed), _position(2, 2, LotPositionKind.MIXED))
    assert not draws_on_raw_material(_lot(mixed), _position(1, 1, LotPositionKind.EXTERNAL))
    alteration = dataclasses.replace(_lot(mixed), source_made_item_id=9)
    assert not draws_on_raw_material(alteration, mixed)


def test_a_made_booking_must_fit_what_the_predecessor_completed() -> None:
    first = _position(1, 1, LotPositionKind.INTERNAL, completed=4.0)
    second = _position(2, 2, LotPositionKind.EXTERNAL)
    lot = _lot(first, second)
    with pytest.raises(LotPositionOverflowError):
        assert_made_booking_fits(
            _made_line(),
            lot,
            second,
            delivered_now=5.0,
            quantity_rejected=0.0,
            rejection_outcome=None,
            accepted_earlier=None,
            raw_material_arrived=None,
        )
    # Pieces an earlier booking of the same transaction accepted on the
    # predecessor count as completed.
    assert_made_booking_fits(
        _made_line(),
        lot,
        second,
        delivered_now=5.0,
        quantity_rejected=0.0,
        rejection_outcome=None,
        accepted_earlier={1: 1.0},
        raw_material_arrived=None,
    )
    assert first.quantity_completed == 4.0


def test_lost_made_pieces_need_a_position_the_lot_can_dispose_on() -> None:
    first = _position(1, 1, LotPositionKind.INTERNAL, completed=10.0)
    internal = _position(2, 2, LotPositionKind.INTERNAL)
    with pytest.raises(LotNotScrappableError):
        assert_made_booking_fits(
            _made_line(),
            _lot(first, internal),
            internal,
            delivered_now=0.0,
            quantity_rejected=2.0,
            rejection_outcome="lost",
            accepted_earlier=None,
            raw_material_arrived=None,
        )


def test_fulfilled_bought_demands_counts_only_bought_demand_statuses() -> None:
    changes = [
        _change(LifecycleAggregate.BOUGHT_DEMANDS, "fulfilled"),
        _change(LifecycleAggregate.BOUGHT_DEMANDS, "ordered"),
        _change(LifecycleAggregate.SOURCE_DEMANDS, "fulfilled"),
    ]
    assert fulfilled_bought_demands(changes) == 1


@pytest.mark.parametrize(
    ("line_status", "order_status", "canceled", "reason"),
    [
        (OrderItemStatus.ORDERED, OrderStatus.CANCELED, True, "canceled"),
        (OrderItemStatus.CANCELED, OrderStatus.ORDERED, False, "canceled"),
        (OrderItemStatus.DELIVERED, OrderStatus.ORDERED, False, "delivered"),
        (OrderItemStatus.PENDING, OrderStatus.ORDERED, False, "not_ordered"),
        (OrderItemStatus.ORDERED, OrderStatus.CANCELED, False, "order_canceled"),
        (OrderItemStatus.PARTIALLY_DELIVERED, OrderStatus.ORDERED, False, "lot_canceled"),
    ],
)
def test_deliver_all_names_why_it_skipped_a_line(
    line_status: OrderItemStatus, order_status: OrderStatus, canceled: bool, reason: str
) -> None:
    line = make_order_item(status=line_status)
    line.canceled_at = _NOW if canceled else None
    assert deliver_all_skip_reason(make_order(status=order_status), line) == reason


def test_deliver_all_books_ordered_and_partially_delivered_lines() -> None:
    assert is_open_for_delivery(make_order_item(status=OrderItemStatus.ORDERED))
    assert is_open_for_delivery(make_order_item(status=OrderItemStatus.PARTIALLY_DELIVERED))
    assert not is_open_for_delivery(make_order_item(status=OrderItemStatus.PENDING))
    assert not is_open_for_delivery(make_order_item(status=OrderItemStatus.DELIVERED))
