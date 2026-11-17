"""
A missing stamp gets the run's time, both when its status is entered in the
run and when the stored status already is the derived one.
"""

from datetime import timedelta

from src.modules.fulfillment.domain.services.lifecycle.snapshot import derive_snapshot
from src.modules.fulfillment.domain.services.lifecycle.stored import LifecycleField
from src.modules.fulfillment.domain.services.lifecycle.stored import lot_changes
from src.modules.fulfillment.domain.services.lifecycle.stored import order_changes
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionKind
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionStatus
from src.modules.fulfillment.domain.value_objects.lot_status import LotStatus
from src.modules.fulfillment.domain.value_objects.order_status import OrderItemStatus
from src.modules.fulfillment.domain.value_objects.order_status import OrderStatus
from src.modules.fulfillment.domain.value_objects.production_status import ProductionOrderStatus
from tests.unit.lifecycle.fake_world import NOW
from tests.unit.lifecycle.fake_world import FakeWorld

EARLIER = NOW - timedelta(days=3)
LATER = NOW + timedelta(hours=2)


def _stamp(changes: list, field: LifecycleField) -> object:  # type: ignore[type-arg]
    [change] = [c for c in changes if c.field is field]
    return change.value


def test_a_stamp_entered_with_its_status_gets_the_run_time() -> None:
    world = FakeWorld()
    order = world.order(status=OrderStatus.ORDERED, ordered_date=NOW, changed=EARLIER)
    world.line(order, status=OrderItemStatus.DELIVERED, ordered_date=NOW, delivered=10.0)
    derived = derive_snapshot(world.snapshot()).orders[order.id]

    assert _stamp(order_changes(order, derived, now=LATER), LifecycleField.DELIVERY_DATE) == LATER


def test_a_stamp_missing_on_a_settled_status_gets_the_run_time() -> None:
    world = FakeWorld()
    lot = world.lot(status=LotStatus.COMPLETED, changed=EARLIER)
    position = world.position(
        lot,
        kind=LotPositionKind.INTERNAL,
        status=LotPositionStatus.COMPLETED,
        quantity_completed=10.0,
    )
    world.production_order(
        position,
        status=ProductionOrderStatus.COMPLETED,
        actual_start=NOW,
        actual_end=NOW,
        processed=10.0,
    )
    derived = derive_snapshot(world.snapshot()).lots[lot.id]

    changes = lot_changes(lot, derived, now=LATER)

    assert [c.field for c in changes] == [LifecycleField.COMPLETED_AT]
    assert _stamp(changes, LifecycleField.COMPLETED_AT) == LATER
