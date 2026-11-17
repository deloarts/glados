"""
lifecycle/stored.py: which stored lifecycle fields differ from their
derivation, and writing the derived values back. Stamps are set when their
status is entered and cleared when it is left, and the completed count is
stored capped at the position quantity.
"""

from dataclasses import replace
from datetime import timedelta

import pytest

from src.modules.catalogue.domain.value_objects.bought_item_status import BoughtItemDemandStatus
from src.modules.fulfillment.domain.services.lifecycle.snapshot import LifecycleSnapshot
from src.modules.fulfillment.domain.services.lifecycle.snapshot import derive_snapshot
from src.modules.fulfillment.domain.services.lifecycle.stored import COMPLETED_COUNT_RULE
from src.modules.fulfillment.domain.services.lifecycle.stored import ORDER_COMPLETED_COUNT_RULE
from src.modules.fulfillment.domain.services.lifecycle.stored import FieldChange
from src.modules.fulfillment.domain.services.lifecycle.stored import LifecycleField
from src.modules.fulfillment.domain.services.lifecycle.stored import apply_lot_changes
from src.modules.fulfillment.domain.services.lifecycle.stored import apply_order_changes
from src.modules.fulfillment.domain.services.lifecycle.stored import apply_order_item_changes
from src.modules.fulfillment.domain.services.lifecycle.stored import apply_position_changes
from src.modules.fulfillment.domain.services.lifecycle.stored import apply_production_order_changes
from src.modules.fulfillment.domain.services.lifecycle.stored import completed_over_quantity
from src.modules.fulfillment.domain.services.lifecycle.stored import demand_changes
from src.modules.fulfillment.domain.services.lifecycle.stored import lot_changes
from src.modules.fulfillment.domain.services.lifecycle.stored import order_changes
from src.modules.fulfillment.domain.services.lifecycle.stored import order_item_changes
from src.modules.fulfillment.domain.services.lifecycle.stored import position_changes
from src.modules.fulfillment.domain.services.lifecycle.stored import production_order_changes
from src.modules.fulfillment.domain.value_objects.lifecycle_aggregate import LifecycleAggregate
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionKind
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionStatus
from src.modules.fulfillment.domain.value_objects.lot_status import LotStatus
from src.modules.fulfillment.domain.value_objects.order_status import OrderItemStatus
from src.modules.fulfillment.domain.value_objects.order_status import OrderStatus
from src.modules.fulfillment.domain.value_objects.production_status import ProductionOrderStatus
from tests.unit.lifecycle.fake_world import NOW
from tests.unit.lifecycle.fake_world import FakeWorld

LATER = NOW + timedelta(hours=2)


def test_a_differing_status_is_one_change_with_its_rule() -> None:
    world = FakeWorld()
    line = world.line(world.order(), status=OrderItemStatus.PENDING, ordered_date=NOW)
    derived = derive_snapshot(world.snapshot()).order_items[line.id]

    [change] = order_item_changes(line, derived)

    assert change == FieldChange(
        aggregate=LifecycleAggregate.ORDER_ITEMS,
        id=line.id,
        field=LifecycleField.STATUS,
        old="pending",
        new="ordered",
        rule="order_item_status row 4: ordered_date set",
        value="ordered",
    )
    apply_order_item_changes(line, [change])
    assert line.status == "ordered"
    assert order_item_changes(line, derived) == []


def test_the_changelog_note_follows_the_status_format() -> None:
    change = FieldChange(
        LifecycleAggregate.ORDERS, 1, LifecycleField.STATUS, "ordered", "delivered", "r", "x"
    )

    assert change.note("delivery recorded") == "Status: ordered → delivered (delivery recorded)."


def test_actual_end_is_set_on_completion_kept_while_completed_and_cleared_after() -> None:
    world = FakeWorld()
    position = world.position(world.lot())
    order = world.production_order(
        position, status=ProductionOrderStatus.IN_PROGRESS, actual_start=NOW, processed=10.0
    )
    completed = derive_snapshot(world.snapshot()).production_orders[order.id]

    changes = production_order_changes(order, completed, now=LATER)

    assert [(c.field, c.new) for c in changes] == [
        (LifecycleField.STATUS, "completed"),
        (LifecycleField.ACTUAL_END, "set"),
    ]
    assert changes[1].note("derived") == "Actual end: set (derived)."
    apply_production_order_changes(order, changes)
    assert (order.status, order.actual_end) == ("completed", LATER)
    # A later run while the order stays completed keeps the first stamp.
    assert production_order_changes(order, completed, now=LATER + timedelta(days=1)) == []

    order.completions = []
    reopened = derive_snapshot(
        LifecycleSnapshot(production_orders={order.id: order})
    ).production_orders[order.id]
    changes = production_order_changes(order, reopened, now=LATER)
    assert [(c.field, c.old, c.new) for c in changes] == [
        (LifecycleField.STATUS, "completed", "in_progress"),
        (LifecycleField.ACTUAL_END, LATER.isoformat(timespec="seconds"), "-"),
        (LifecycleField.QUANTITY_COMPLETED, "10", "0"),
    ]
    assert changes[1].note("derived") == "Actual end: cleared (derived)."
    apply_production_order_changes(order, changes)
    assert order.actual_end is None


def test_a_completed_or_canceled_order_drops_its_planned_window() -> None:
    world = FakeWorld()
    position = world.position(world.lot())
    order = world.production_order(
        position, status=ProductionOrderStatus.IN_PROGRESS, actual_start=NOW, processed=10.0
    )
    order.planned_start, order.planned_end, order.planned_by_id = NOW, LATER, 7
    order.planned_end_at_start = LATER
    completed = derive_snapshot(world.snapshot()).production_orders[order.id]

    apply_production_order_changes(order, production_order_changes(order, completed, now=LATER))

    assert (order.planned_start, order.planned_end, order.planned_by_id) == (None, None, None)
    assert (order.actual_start, order.planned_end_at_start) == (NOW, LATER)

    queued = world.production_order(
        world.position(world.lot()), status=ProductionOrderStatus.QUEUED
    )
    queued.planned_start, queued.planned_end = NOW, LATER
    queued.canceled_at = NOW
    canceled = derive_snapshot(world.snapshot()).production_orders[queued.id]

    apply_production_order_changes(queued, production_order_changes(queued, canceled, now=LATER))

    assert queued.status == "canceled"
    assert (queued.planned_start, queued.planned_end) == (None, None)


def test_a_production_order_stores_the_accepted_pieces_of_its_completion_rows() -> None:
    world = FakeWorld()
    position = world.position(world.lot())
    order = world.production_order(
        position,
        status=ProductionOrderStatus.IN_PROGRESS,
        actual_start=NOW,
        processed=6.0,
        quantity_completed=4.0,
    )
    order.quantity_completed = 0.0
    derived = derive_snapshot(world.snapshot()).production_orders[order.id]

    [change] = production_order_changes(order, derived, now=LATER)

    assert (change.field, change.old, change.new, change.value) == (
        LifecycleField.QUANTITY_COMPLETED,
        "0",
        "4",
        4.0,
    )
    assert change.rule == ORDER_COMPLETED_COUNT_RULE
    apply_production_order_changes(order, [change])
    assert order.quantity_completed == 4.0
    assert production_order_changes(order, derived, now=LATER) == []


def test_a_reversed_completion_nets_out_of_the_stored_count() -> None:
    world = FakeWorld()
    position = world.position(world.lot())
    order = world.production_order(
        position, status=ProductionOrderStatus.IN_PROGRESS, actual_start=NOW, processed=4.0
    )
    [booked] = order.completions
    order.completions.append(
        replace(
            booked,
            id=world.next_id(),
            quantity=-booked.quantity,
            quantity_accepted=-booked.quantity_accepted,
            quantity_rejected=0.0,
            reverses_completion_id=booked.id,
        )
    )
    derived = derive_snapshot(world.snapshot()).production_orders[order.id]

    [change] = production_order_changes(order, derived, now=LATER)

    assert (change.field, change.old, change.new) == (LifecycleField.QUANTITY_COMPLETED, "4", "0")


def test_a_position_counts_the_completion_rows_not_the_stored_order_count() -> None:
    world = FakeWorld()
    position = world.position(
        world.lot(), kind=LotPositionKind.INTERNAL, status=LotPositionStatus.PARTIALLY_COMPLETED
    )
    order = world.production_order(
        position, status=ProductionOrderStatus.IN_PROGRESS, actual_start=NOW, processed=4.0
    )
    order.quantity_completed = 0.0

    derived = derive_snapshot(world.snapshot()).positions[position.id]

    assert derived.quantity_completed == 4.0


def test_a_lot_gets_completed_at_exactly_while_it_is_completed() -> None:
    world = FakeWorld()
    lot = world.lot(status=LotStatus.IN_PROGRESS)
    position = world.position(lot)
    world.production_order(
        position, status=ProductionOrderStatus.COMPLETED, actual_start=NOW, processed=10.0
    )
    derived = derive_snapshot(world.snapshot()).lots[lot.id]

    changes = lot_changes(lot, derived, now=LATER)
    apply_lot_changes(lot, changes)

    assert (lot.status, lot.completed_at) == ("completed", LATER)
    stale = world.lot(status=LotStatus.IN_PROGRESS, completed_at=NOW)
    world.position(stale)
    stale_derived = derive_snapshot(world.snapshot()).lots[stale.id]
    assert [(c.field, c.new) for c in lot_changes(stale, stale_derived, now=LATER)] == [
        (LifecycleField.STATUS, "draft"),
        (LifecycleField.COMPLETED_AT, "-"),
    ]


def test_an_order_gets_its_delivery_date_exactly_while_it_is_delivered() -> None:
    world = FakeWorld()
    order = world.order(status=OrderStatus.ORDERED, ordered_date=NOW)
    world.line(order, status=OrderItemStatus.DELIVERED, ordered_date=NOW, delivered=10.0)
    derived = derive_snapshot(world.snapshot()).orders[order.id]

    changes = order_changes(order, derived, now=LATER)
    apply_order_changes(order, changes)

    assert (order.status, order.delivery_date) == ("delivered", LATER)
    assert order_changes(order, derived, now=LATER) == []


def test_a_position_compares_kind_status_and_completed_count() -> None:
    world = FakeWorld()
    position = world.position(
        world.lot(), kind=LotPositionKind.UNASSIGNED, status=LotPositionStatus.PENDING
    )
    world.production_order(
        position, status=ProductionOrderStatus.IN_PROGRESS, actual_start=NOW, processed=4.0
    )
    derived = derive_snapshot(world.snapshot()).positions[position.id]

    changes = position_changes(position, derived)

    assert [(c.field, c.old, c.new) for c in changes] == [
        (LifecycleField.KIND, "unassigned", "internal"),
        (LifecycleField.STATUS, "pending", "partially_completed"),
        (LifecycleField.QUANTITY_COMPLETED, "0", "4"),
    ]
    assert changes[2].rule == COMPLETED_COUNT_RULE
    assert changes[2].note("derived") == "Completed quantity: 0 → 4 (derived)."
    apply_position_changes(position, changes)
    assert (position.kind, position.status, position.quantity_completed) == (
        "internal",
        "partially_completed",
        4.0,
    )


def test_the_completed_count_compares_within_the_tolerance() -> None:
    world = FakeWorld()
    position = world.position(
        world.lot(), kind=LotPositionKind.INTERNAL, status=LotPositionStatus.PARTIALLY_COMPLETED
    )
    world.production_order(
        position, status=ProductionOrderStatus.IN_PROGRESS, actual_start=NOW, processed=4.0
    )
    position.quantity_completed = 4.0000001
    derived = derive_snapshot(world.snapshot()).positions[position.id]

    assert position_changes(position, derived) == []


def test_the_stored_count_is_capped_and_the_excess_is_an_anomaly() -> None:
    world = FakeWorld()
    position = world.position(
        world.lot(quantity=10.0), kind=LotPositionKind.INTERNAL, status=LotPositionStatus.COMPLETED
    )
    world.production_order(
        position, status=ProductionOrderStatus.COMPLETED, actual_start=NOW, processed=12.0
    )
    derived = derive_snapshot(world.snapshot()).positions[position.id]

    [change] = position_changes(position, derived)

    assert (change.field, change.value) == (LifecycleField.QUANTITY_COMPLETED, 10.0)
    assert completed_over_quantity(position, derived)
    position.quantity_completed = 10.0
    assert position_changes(position, derived) == []


def test_a_bought_demand_compares_its_status() -> None:
    world = FakeWorld()
    demand = world.bought_demand(status=BoughtItemDemandStatus.OPEN)
    world.allocate_bought(demand, None, 10.0)
    derived = derive_snapshot(world.snapshot()).bought_demands[demand.id]

    [change] = demand_changes(LifecycleAggregate.BOUGHT_DEMANDS, demand, derived)

    assert (change.aggregate, change.old, change.new) == (
        LifecycleAggregate.BOUGHT_DEMANDS,
        "open",
        "fulfilled",
    )


def test_a_write_refuses_a_field_the_aggregate_does_not_store() -> None:
    world = FakeWorld()
    line = world.line(world.order())
    kind = FieldChange(
        LifecycleAggregate.ORDER_ITEMS, line.id, LifecycleField.KIND, "a", "b", "r", "b"
    )
    wrong_type = FieldChange(
        LifecycleAggregate.ORDER_ITEMS, line.id, LifecycleField.STATUS, "a", "b", "r", 1.0
    )

    with pytest.raises(ValueError):
        apply_order_item_changes(line, [kind])
    with pytest.raises(TypeError):
        apply_order_item_changes(line, [wrong_type])
