"""
A position holds at most one live order line and any number of canceled
ones beside it. Its kind and status derive from the live line whatever the
ids, and from the newest canceled line only while no live one exists.
"""

from datetime import UTC
from datetime import datetime

from src.modules.fulfillment.domain.services.lifecycle.snapshot import derive_snapshot
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionKind
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionStatus
from src.modules.fulfillment.domain.value_objects.order_status import OrderItemStatus
from src.modules.fulfillment.domain.value_objects.order_status import OrderStatus
from tests.unit.lifecycle.fake_world import NOW
from tests.unit.lifecycle.fake_world import FakeWorld

CANCELED = datetime(2026, 1, 3, tzinfo=UTC)


def test_the_live_line_wins_over_a_newer_canceled_one() -> None:
    world = FakeWorld()
    lot = world.lot()
    position = world.position(lot)
    live_order = world.order(status=OrderStatus.ORDERED, ordered_date=NOW)
    world.line(
        live_order,
        status=OrderItemStatus.ORDERED,
        ordered_date=NOW,
        quantity=7.0,
        position=position,
    )
    dropped_order = world.order(status=OrderStatus.CANCELED, canceled_at=CANCELED)
    world.line(
        dropped_order, status=OrderItemStatus.CANCELED, canceled_at=CANCELED, position=position
    )

    derived = derive_snapshot(world.snapshot()).positions[position.id]

    assert derived.kind.value is LotPositionKind.EXTERNAL
    assert derived.status.value is LotPositionStatus.ORDERED_OR_QUEUED
    assert derived.status.facts.line is not None
    assert derived.status.facts.line.status is OrderItemStatus.ORDERED
    assert derived.status.facts.line.quantity == 7.0


def test_the_live_line_wins_over_an_older_canceled_one() -> None:
    world = FakeWorld()
    lot = world.lot()
    position = world.position(lot)
    dropped_order = world.order(status=OrderStatus.CANCELED, canceled_at=CANCELED)
    world.line(
        dropped_order, status=OrderItemStatus.CANCELED, canceled_at=CANCELED, position=position
    )
    live_order = world.order(status=OrderStatus.ORDERED, ordered_date=NOW)
    world.line(
        live_order,
        status=OrderItemStatus.ORDERED,
        ordered_date=NOW,
        quantity=7.0,
        position=position,
    )

    derived = derive_snapshot(world.snapshot()).positions[position.id]

    assert derived.kind.value is LotPositionKind.EXTERNAL
    assert derived.status.facts.line is not None
    assert (derived.status.facts.line.status, derived.status.facts.line.quantity) == (
        OrderItemStatus.ORDERED,
        7.0,
    )


def test_without_a_live_line_the_newest_canceled_one_is_read() -> None:
    world = FakeWorld()
    lot = world.lot()
    position = world.position(lot)
    first = world.order(status=OrderStatus.CANCELED, canceled_at=CANCELED)
    world.line(first, status=OrderItemStatus.CANCELED, canceled_at=CANCELED, position=position)
    second = world.order(status=OrderStatus.CANCELED, canceled_at=CANCELED)
    world.line(
        second,
        status=OrderItemStatus.CANCELED,
        canceled_at=CANCELED,
        quantity=3.0,
        position=position,
    )

    derived = derive_snapshot(world.snapshot()).positions[position.id]

    assert derived.kind.value is LotPositionKind.UNASSIGNED
    assert derived.status.value is LotPositionStatus.PENDING
    assert derived.status.facts.line is not None
    assert (derived.status.facts.line.status, derived.status.facts.line.quantity) == (
        OrderItemStatus.CANCELED,
        3.0,
    )
