"""
lifecycle/stored.py on an order's ordered_date: recorded the first time the
order derives ORDERED without one, as when its lines were all marked ordered
one by one, kept as it is once set, and never cleared when the order leaves
ORDERED.
"""

from datetime import timedelta

from src.modules.fulfillment.domain.services.lifecycle.snapshot import derive_snapshot
from src.modules.fulfillment.domain.services.lifecycle.stored import LifecycleField
from src.modules.fulfillment.domain.services.lifecycle.stored import apply_order_changes
from src.modules.fulfillment.domain.services.lifecycle.stored import order_changes
from src.modules.fulfillment.domain.value_objects.order_status import OrderItemStatus
from src.modules.fulfillment.domain.value_objects.order_status import OrderStatus
from tests.unit.lifecycle.fake_world import NOW
from tests.unit.lifecycle.fake_world import FakeWorld

LATER = NOW + timedelta(hours=2)


def test_an_order_whose_lines_are_all_ordered_records_its_ordered_date() -> None:
    world = FakeWorld()
    order = world.order(status=OrderStatus.DRAFT)
    world.line(order, status=OrderItemStatus.ORDERED, ordered_date=NOW)
    world.line(order, status=OrderItemStatus.ORDERED, ordered_date=NOW)
    derived = derive_snapshot(world.snapshot()).orders[order.id]

    changes = order_changes(order, derived, now=LATER)

    assert [(c.field, c.old, c.new) for c in changes] == [
        (LifecycleField.STATUS, "draft", "ordered"),
        (LifecycleField.ORDERED_DATE, "-", "set"),
    ]
    assert changes[1].note("derived") == "Ordered date: set (derived)."
    apply_order_changes(order, changes)
    assert (order.status, order.ordered_date) == ("ordered", LATER)
    # The recorded date keeps the order ORDERED and is not written again.
    rederived = derive_snapshot(world.snapshot()).orders[order.id]
    assert order_changes(order, rederived, now=LATER + timedelta(days=1)) == []


def test_a_recorded_ordered_date_is_kept() -> None:
    world = FakeWorld()
    order = world.order(status=OrderStatus.ORDERED, ordered_date=NOW)
    world.line(order, status=OrderItemStatus.ORDERED, ordered_date=NOW)
    derived = derive_snapshot(world.snapshot()).orders[order.id]

    assert order_changes(order, derived, now=LATER) == []


def test_the_ordered_date_is_never_cleared() -> None:
    world = FakeWorld()
    order = world.order(status=OrderStatus.ORDERED, ordered_date=NOW)
    world.line(order, status=OrderItemStatus.ORDERED, ordered_date=NOW, canceled_at=NOW)
    derived = derive_snapshot(world.snapshot()).orders[order.id]

    changes = order_changes(order, derived, now=LATER)

    # Every line canceled: the order derives CANCELED and keeps its date.
    assert [(c.field, c.new) for c in changes] == [(LifecycleField.STATUS, "canceled")]
    apply_order_changes(order, changes)
    assert order.ordered_date == NOW


def test_an_order_that_is_not_ordered_records_no_ordered_date() -> None:
    world = FakeWorld()
    order = world.order(status=OrderStatus.DRAFT)
    world.line(order, status=OrderItemStatus.ORDERED, ordered_date=NOW)
    world.line(order, status=OrderItemStatus.PENDING)
    derived = derive_snapshot(world.snapshot()).orders[order.id]

    # Partially ordered is not ordered: only the status changes.
    changes = order_changes(order, derived, now=LATER)
    assert [(c.field, c.new) for c in changes] == [(LifecycleField.STATUS, "partially_ordered")]
