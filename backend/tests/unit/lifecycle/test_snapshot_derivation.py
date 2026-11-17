"""
derive_snapshot composes the lifecycle tables over loaded entities: every
aggregate reads the derived values of its inputs, never their stored
statuses, and a reference the snapshot does not hold derives as covering
nothing.
"""

from src.modules.catalogue.domain.value_objects.bought_item_status import BoughtItemDemandStatus
from src.modules.catalogue.domain.value_objects.made_item_status import MadeItemDemandStatus
from src.modules.fulfillment.domain.services.lifecycle.snapshot import LifecycleSnapshot
from src.modules.fulfillment.domain.services.lifecycle.snapshot import derive_snapshot
from src.modules.fulfillment.domain.value_objects.interruption_reason import InterruptionReason
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionKind
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionStatus
from src.modules.fulfillment.domain.value_objects.lot_status import LotStatus
from src.modules.fulfillment.domain.value_objects.order_status import OrderItemStatus
from src.modules.fulfillment.domain.value_objects.order_status import OrderStatus
from src.modules.fulfillment.domain.value_objects.production_status import ProductionOrderStatus
from src.modules.fulfillment.domain.value_objects.source_item_demand_status import (
    SourceItemDemandStatus,
)
from tests.unit.lifecycle.fake_world import NOW
from tests.unit.lifecycle.fake_world import FakeWorld


def test_a_position_reads_its_lines_derived_status_not_the_stored_one() -> None:
    world = FakeWorld()
    lot = world.lot()
    position = world.position(lot)
    order = world.order(status=OrderStatus.ORDERED, ordered_date=NOW)
    # Stored as pending, but its ordered date makes it ordered.
    line = world.line(order, status=OrderItemStatus.PENDING, ordered_date=NOW, position=position)

    derivation = derive_snapshot(world.snapshot())

    assert derivation.order_items[line.id].value is OrderItemStatus.ORDERED
    derived = derivation.positions[position.id]
    assert derived.kind.value is LotPositionKind.EXTERNAL
    assert derived.status.value is LotPositionStatus.ORDERED_OR_QUEUED
    assert derived.status.facts.line is not None
    assert derived.status.facts.line.status is OrderItemStatus.ORDERED


def test_a_lot_reads_the_derived_statuses_of_its_positions() -> None:
    world = FakeWorld()
    lot = world.lot(status=LotStatus.IN_PROGRESS)
    first = world.position(lot, status=LotPositionStatus.PENDING)
    second = world.position(lot, status=LotPositionStatus.PENDING)
    world.production_order(
        first, status=ProductionOrderStatus.IN_PROGRESS, actual_start=NOW, processed=10.0
    )
    order = world.order(status=OrderStatus.ORDERED, ordered_date=NOW)
    world.line(
        order, status=OrderItemStatus.ORDERED, ordered_date=NOW, delivered=10.0, position=second
    )

    derivation = derive_snapshot(world.snapshot())

    assert derivation.positions[first.id].status.value is LotPositionStatus.COMPLETED
    assert derivation.positions[second.id].status.value is LotPositionStatus.COMPLETED
    lot_derived = derivation.lots[lot.id]
    assert lot_derived.status.value is LotStatus.COMPLETED
    assert lot_derived.status.rule.table == "lot_status"
    assert lot_derived.status.rule.number == 3
    assert lot_derived.quantity_completed == 10.0


def test_the_lot_completed_count_is_the_last_positions_by_sequence() -> None:
    world = FakeWorld()
    lot = world.lot()
    late = world.position(lot, sequence=2)
    early = world.position(lot, sequence=1)
    world.production_order(
        early, status=ProductionOrderStatus.IN_PROGRESS, actual_start=NOW, processed=8.0
    )
    world.production_order(
        late, status=ProductionOrderStatus.IN_PROGRESS, actual_start=NOW, processed=3.0
    )

    derivation = derive_snapshot(world.snapshot())

    assert derivation.lots[lot.id].quantity_completed == 3.0
    assert derivation.lots[lot.id].status.facts.position_statuses == (
        LotPositionStatus.PARTIALLY_COMPLETED,
        LotPositionStatus.PARTIALLY_COMPLETED,
    )


def test_an_order_with_a_delivered_and_a_canceled_line_is_delivered() -> None:
    world = FakeWorld()
    order = world.order(status=OrderStatus.PARTIALLY_DELIVERED, ordered_date=NOW)
    world.line(order, status=OrderItemStatus.DELIVERED, ordered_date=NOW, delivered=10.0)
    world.line(order, status=OrderItemStatus.ORDERED, ordered_date=NOW, canceled_at=NOW)

    derived = derive_snapshot(world.snapshot()).orders[order.id]

    assert derived.value is OrderStatus.DELIVERED
    assert derived.facts.line_statuses == (OrderItemStatus.DELIVERED, OrderItemStatus.CANCELED)


def test_a_production_order_counts_processed_pieces_and_its_open_interruption() -> None:
    world = FakeWorld()
    position = world.position(world.lot())
    paused = world.production_order(
        position,
        actual_start=NOW,
        processed=4.0,
        quantity_completed=3.0,
        open_interruption=InterruptionReason.LOT_HOLD,
    )
    done = world.production_order(position, actual_start=NOW, quantity=5.0, processed=5.0)

    derivation = derive_snapshot(world.snapshot())

    assert derivation.production_orders[paused.id].value is ProductionOrderStatus.PAUSED
    facts = derivation.production_orders[paused.id].facts
    assert facts.processed == 4.0
    assert facts.open_interruption is InterruptionReason.LOT_HOLD
    assert derivation.production_orders[done.id].value is ProductionOrderStatus.COMPLETED


def test_a_canceled_lot_cancels_its_positions_and_keeps_their_progress_count() -> None:
    world = FakeWorld()
    lot = world.lot(canceled_at=NOW)
    position = world.position(lot)
    world.production_order(
        position, status=ProductionOrderStatus.CANCELED, canceled_at=NOW, processed=4.0
    )

    derived = derive_snapshot(world.snapshot()).positions[position.id]

    assert derived.status.value is LotPositionStatus.CANCELED
    assert derived.kind.value is LotPositionKind.INTERNAL
    assert derived.quantity_completed == 4.0


def test_the_derived_completed_count_is_not_capped_at_the_position_quantity() -> None:
    world = FakeWorld()
    position = world.position(world.lot(quantity=10.0))
    world.production_order(position, actual_start=NOW, quantity=10.0, processed=12.0)

    assert derive_snapshot(world.snapshot()).positions[position.id].quantity_completed == 12.0


def test_bought_and_source_demands_read_their_lines_derived_status_and_totals() -> None:
    world = FakeWorld()
    order = world.order(status=OrderStatus.ORDERED, ordered_date=NOW)
    line = world.line(
        order, status=OrderItemStatus.PENDING, ordered_date=NOW, quantity=10.0, delivered=4.0
    )
    bought = world.bought_demand(quantity=6.0)
    world.allocate_bought(bought, line, 4.0)
    world.allocate_bought(bought, None, 2.0)
    source = world.source_demand(quantity=10.0)
    world.allocate_source(source, line, 10.0)

    derivation = derive_snapshot(world.snapshot())

    # The 4 pieces that arrived fill the bought demand first, which comes
    # before every source demand on the line; with its 2 from stock it is
    # fulfilled, and nothing has reached the source demand yet.
    bought_derived = derivation.bought_demands[bought.id]
    assert bought_derived.value is BoughtItemDemandStatus.FULFILLED
    allocations = bought_derived.facts.allocations
    assert [a.from_stock for a in allocations] == [True, False]
    assert allocations[1].line is not None
    assert allocations[1].line.status is OrderItemStatus.PARTIALLY_DELIVERED
    assert derivation.source_demands[source.id].value is SourceItemDemandStatus.ORDERED


def test_a_made_demand_reads_its_lots_derived_status_and_completed_count() -> None:
    world = FakeWorld()
    lot = world.lot(quantity=10.0, status=LotStatus.DRAFT)
    position = world.position(lot)
    world.production_order(position, actual_start=NOW, processed=10.0)
    demand = world.made_demand(quantity=10.0, status=MadeItemDemandStatus.ALLOCATED)
    world.allocate_made(demand, lot, 10.0)

    derived = derive_snapshot(world.snapshot()).made_demands[demand.id]

    assert derived.value is MadeItemDemandStatus.FULFILLED
    [allocation] = derived.facts.allocations
    assert allocation.lot is not None
    assert allocation.lot.status is LotStatus.COMPLETED
    assert allocation.lot.quantity_completed == 10.0


def test_an_allocation_whose_line_or_lot_is_not_loaded_covers_nothing() -> None:
    world = FakeWorld()
    order = world.order(status=OrderStatus.ORDERED, ordered_date=NOW)
    line = world.line(order, status=OrderItemStatus.DELIVERED, ordered_date=NOW, delivered=10.0)
    bought = world.bought_demand(quantity=10.0, status=BoughtItemDemandStatus.FULFILLED)
    world.allocate_bought(bought, line, 10.0)
    lot = world.lot()
    made = world.made_demand(quantity=10.0)
    world.allocate_made(made, lot, 10.0)
    full = world.snapshot()

    partial = LifecycleSnapshot(
        bought_demands=full.bought_demands,
        bought_allocations=full.bought_allocations,
        made_demands=full.made_demands,
        made_allocations=full.made_allocations,
    )
    derivation = derive_snapshot(partial)

    [bought_allocation] = derivation.bought_demands[bought.id].facts.allocations
    assert bought_allocation.line is None
    assert not bought_allocation.from_stock
    assert derivation.bought_demands[bought.id].value is BoughtItemDemandStatus.ALLOCATED
    assert derivation.made_demands[made.id].facts.allocations[0].lot is None


def test_every_derived_value_names_its_table_row() -> None:
    world = FakeWorld()
    line = world.line(world.order(), status=OrderItemStatus.PENDING, canceled_at=NOW)

    rule = derive_snapshot(world.snapshot()).order_items[line.id].rule

    assert (rule.table, rule.number, rule.condition) == ("order_item_status", 1, "canceled_at set")
    assert str(rule) == "order_item_status row 1: canceled_at set"
