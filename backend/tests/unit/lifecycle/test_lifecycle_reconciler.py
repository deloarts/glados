"""
LifecycleReconciler on the fake world: it widens what was touched to its
dependents, locks only those targets in the lock order, derives everything
from facts, writes only the fields that differ with one changelog line each,
publishes the events of the status changes and changes nothing when run
again.
"""

import pytest

from src.modules.catalogue.domain.events.bought_item_events import DemandItemStatusChanged
from src.modules.catalogue.domain.events.made_item_events import MadeItemDemandItemStatusChanged
from src.modules.catalogue.domain.value_objects.bought_item_status import BoughtItemDemandStatus
from src.modules.catalogue.domain.value_objects.made_item_status import MadeItemDemandStatus
from src.modules.fulfillment.application.services.lifecycle_loader import AggregateIds
from src.modules.fulfillment.application.services.lifecycle_lock_plan import LockOrderError
from src.modules.fulfillment.application.services.lifecycle_lock_plan import LockPlan
from src.modules.fulfillment.application.services.lifecycle_reconciler import DEFAULT_REASON
from src.modules.fulfillment.application.services.lifecycle_reconciler import LifecycleReconciler
from src.modules.fulfillment.application.services.lifecycle_reconciler import assert_reconcilable
from src.modules.fulfillment.domain.events.lot_events import LotCompleted
from src.modules.fulfillment.domain.events.lot_events import LotPositionStatusChanged
from src.modules.fulfillment.domain.events.lot_events import LotStatusChanged
from src.modules.fulfillment.domain.events.order_events import OrderItemStatusChanged
from src.modules.fulfillment.domain.events.order_events import OrderStatusChanged
from src.modules.fulfillment.domain.events.production_order_events import ProductionOrderCanceled
from src.modules.fulfillment.domain.events.production_order_events import ProductionOrderCompleted
from src.modules.fulfillment.domain.events.source_item_demand_events import (
    SourceItemDemandStatusChanged,
)
from src.modules.fulfillment.domain.services.lifecycle.stored import LifecycleField
from src.modules.fulfillment.domain.value_objects.lifecycle_aggregate import DEMAND_AGGREGATES
from src.modules.fulfillment.domain.value_objects.lifecycle_aggregate import LifecycleAggregate
from src.modules.fulfillment.domain.value_objects.lot_event_type import LotEventType
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionKind
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionStatus
from src.modules.fulfillment.domain.value_objects.lot_status import LotStatus
from src.modules.fulfillment.domain.value_objects.order_status import OrderItemStatus
from src.modules.fulfillment.domain.value_objects.order_status import OrderLineType
from src.modules.fulfillment.domain.value_objects.order_status import OrderStatus
from src.modules.fulfillment.domain.value_objects.production_status import ProductionOrderStatus
from src.modules.fulfillment.domain.value_objects.source_item_demand_status import (
    SourceItemDemandStatus,
)
from tests.unit.fakes import FakeEventBus
from tests.unit.lifecycle.fake_world import NOW
from tests.unit.lifecycle.fake_world import FakeWorld
from tests.unit.lifecycle.fake_world import actor

_A = LifecycleAggregate
ALL = frozenset(LifecycleAggregate)
ACTOR = actor()


def _reconciler(
    world: FakeWorld, aggregates: frozenset[LifecycleAggregate] = ALL
) -> tuple[LifecycleReconciler, FakeEventBus]:
    bus = FakeEventBus()
    return LifecycleReconciler(world.repositories, bus, aggregates=aggregates), bus


def _delivered_made_line(world: FakeWorld) -> dict[str, int]:
    """A lot of one position whose MADE line has been delivered in full while
    every stored status still says ordered, with a made demand on the lot."""
    lot = world.lot(status=LotStatus.PLANNED)
    position = world.position(
        lot, kind=LotPositionKind.EXTERNAL, status=LotPositionStatus.ORDERED_OR_QUEUED
    )
    order = world.order(status=OrderStatus.ORDERED, ordered_date=NOW)
    line = world.line(
        order, status=OrderItemStatus.ORDERED, ordered_date=NOW, delivered=10.0, position=position
    )
    demand = world.made_demand(status=MadeItemDemandStatus.ORDERED)
    world.allocate_made(demand, lot, 10.0)
    return {
        "lot": lot.id,
        "position": position.id,
        "order": order.id,
        "line": line.id,
        "demand": demand.id,
    }


async def test_nothing_enabled_reads_nothing() -> None:
    world = FakeWorld()
    ids = _delivered_made_line(world)
    reconciler, bus = _reconciler(world, frozenset())
    reconciler.touch_order_items([ids["line"]])

    result = await reconciler.run(ACTOR, NOW)

    assert result.changes == ()
    assert (world.reads, world.lock_log, world.saves, bus.published) == (0, [], [], [])


async def test_nothing_touched_changes_nothing() -> None:
    world = FakeWorld()
    _delivered_made_line(world)
    reconciler, _ = _reconciler(world)

    result = await reconciler.run(ACTOR, NOW)

    assert result.changes == ()
    assert world.reads == 0


async def test_a_delivery_is_carried_bottom_up_through_line_position_lot_order_and_demand() -> None:
    world = FakeWorld()
    ids = _delivered_made_line(world)
    reconciler, _ = _reconciler(world)
    reconciler.touch_order_items([ids["line"]])

    result = await reconciler.run(ACTOR, NOW)

    assert [(c.aggregate, c.field, c.new) for c in result.changes] == [
        (_A.ORDER_ITEMS, LifecycleField.STATUS, "delivered"),
        (_A.LOT_POSITIONS, LifecycleField.STATUS, "completed"),
        (_A.LOT_POSITIONS, LifecycleField.QUANTITY_COMPLETED, "10"),
        (_A.LOTS, LifecycleField.STATUS, "completed"),
        (_A.LOTS, LifecycleField.COMPLETED_AT, "set"),
        (_A.ORDERS, LifecycleField.STATUS, "delivered"),
        (_A.ORDERS, LifecycleField.DELIVERY_DATE, "set"),
        (_A.MADE_DEMANDS, LifecycleField.STATUS, "fulfilled"),
    ]
    assert world.order_items[ids["line"]].status == "delivered"
    assert world.positions[ids["position"]].status == "completed"
    assert (world.lots[ids["lot"]].status, world.lots[ids["lot"]].completed_at) == (
        "completed",
        NOW,
    )
    assert world.orders[ids["order"]].delivery_date == NOW
    assert world.made_demands[ids["demand"]].status == "fulfilled"


async def test_a_second_run_changes_nothing() -> None:
    world = FakeWorld()
    ids = _delivered_made_line(world)
    reconciler, bus = _reconciler(world)
    reconciler.touch_order_items([ids["line"]])
    await reconciler.run(ACTOR, NOW)
    saves, published = len(world.saves), len(bus.published)

    reconciler.touch_order_items([ids["line"]])
    result = await reconciler.run(ACTOR, NOW)

    assert result.changes == ()
    assert (len(world.saves), len(bus.published)) == (saves, published)


async def test_each_changed_field_gets_one_changelog_line_and_changed_is_stamped() -> None:
    world = FakeWorld()
    ids = _delivered_made_line(world)
    reconciler, _ = _reconciler(world)
    reconciler.touch_order_items([ids["line"]])

    await reconciler.run(ACTOR, NOW, reason="delivery recorded")

    lot = world.lots[ids["lot"]]
    assert [line.split(", ", 2)[1:] for line in lot.changes] == [
        ["Pat Planner", "Status: planned → completed (delivery recorded)."],
        ["Pat Planner", "Completed at: set (delivery recorded)."],
    ]
    assert lot.changed == NOW
    demand = world.made_demands[ids["demand"]]
    assert demand.changed == NOW
    assert demand.changes[-1].endswith("Status: ordered → fulfilled (delivery recorded).")
    assert (
        world.order_items[ids["line"]]
        .changes[-1]
        .endswith("Status: ordered → delivered (delivery recorded).")
    )


async def test_the_default_reason_closes_the_changelog_line() -> None:
    world = FakeWorld()
    line = world.line(world.order(), status=OrderItemStatus.PENDING, ordered_date=NOW)
    reconciler, _ = _reconciler(world, frozenset({_A.ORDER_ITEMS}))
    reconciler.touch_order_items([line.id])

    await reconciler.run(ACTOR, NOW)

    assert (
        world.order_items[line.id]
        .changes[-1]
        .endswith(f"Status: pending → ordered ({DEFAULT_REASON}).")
    )


async def test_only_changed_rows_are_saved() -> None:
    world = FakeWorld()
    order = world.order(status=OrderStatus.ORDERED, ordered_date=NOW)
    settled = world.line(order, status=OrderItemStatus.ORDERED, ordered_date=NOW)
    drifted = world.line(order, status=OrderItemStatus.PENDING, ordered_date=NOW)
    reconciler, _ = _reconciler(world, frozenset({_A.ORDER_ITEMS, _A.ORDERS}))
    reconciler.touch_order_items([settled.id, drifted.id])

    await reconciler.run(ACTOR, NOW)

    assert world.saves == [(_A.ORDER_ITEMS, drifted.id)]


async def test_a_delivery_on_a_shared_order_locks_neither_the_other_lines_nor_their_lots() -> None:
    world = FakeWorld()
    lot = world.lot(status=LotStatus.PLANNED)
    other_lot = world.lot(status=LotStatus.PLANNED)
    position = world.position(
        lot, kind=LotPositionKind.EXTERNAL, status=LotPositionStatus.ORDERED_OR_QUEUED
    )
    other_position = world.position(
        other_lot, kind=LotPositionKind.EXTERNAL, status=LotPositionStatus.ORDERED_OR_QUEUED
    )
    order = world.order(status=OrderStatus.ORDERED, ordered_date=NOW)
    line = world.line(
        order, status=OrderItemStatus.ORDERED, ordered_date=NOW, delivered=10.0, position=position
    )
    other_line = world.line(
        order, status=OrderItemStatus.ORDERED, ordered_date=NOW, position=other_position
    )
    reconciler, _ = _reconciler(world)
    reconciler.touch_order_items([line.id])

    await reconciler.run(ACTOR, NOW)

    assert world.locked(_A.LOTS) == {lot.id}
    assert world.locked(_A.ORDER_ITEMS) == {line.id}
    assert other_line.id not in {row_id for _, row_id in world.saves}
    # The order still reads its other line, so it is partly delivered.
    assert world.orders[order.id].status == "partially_delivered"
    assert world.lots[other_lot.id].status == "planned"


async def test_an_input_that_is_no_target_derives_from_its_facts_not_its_stored_status() -> None:
    world = FakeWorld()
    order = world.order(status=OrderStatus.ORDERED, ordered_date=NOW)
    line = world.line(order, status=OrderItemStatus.ORDERED, ordered_date=NOW, delivered=10.0)
    # Stored as delivered, but nothing has arrived on it.
    sibling = world.line(order, status=OrderItemStatus.DELIVERED, ordered_date=NOW)
    reconciler, _ = _reconciler(world)
    reconciler.touch_order_items([line.id])

    await reconciler.run(ACTOR, NOW)

    assert world.orders[order.id].status == "partially_delivered"
    assert world.order_items[sibling.id].status == "delivered"


async def test_aggregates_not_reconciled_are_neither_locked_nor_written() -> None:
    world = FakeWorld()
    ids = _delivered_made_line(world)
    reconciler, bus = _reconciler(world, frozenset({_A.ORDER_ITEMS, _A.ORDERS}))
    reconciler.touch_order_items([ids["line"]])

    await reconciler.run(ACTOR, NOW)

    assert {aggregate for aggregate, _ in world.lock_log} == {_A.ORDERS, _A.ORDER_ITEMS}
    assert {aggregate for aggregate, _ in world.saves} == {_A.ORDERS, _A.ORDER_ITEMS}
    assert world.lots[ids["lot"]].status == "planned"
    assert world.made_demands[ids["demand"]].status == "ordered"
    # Only the written line and order publish their status events.
    assert [type(e) for e in bus.published] == [OrderItemStatusChanged, OrderStatusChanged]


async def test_lock_touched_locks_no_target_of_an_aggregate_not_reconciled() -> None:
    world = FakeWorld()
    ids = _delivered_made_line(world)
    reconciler, _ = _reconciler(world, frozenset({_A.ORDER_ITEMS, _A.ORDERS}))
    reconciler.touch_order_items([ids["line"]])

    await reconciler.lock_touched()

    assert world.lock_log == [(_A.ORDERS, (ids["order"],)), (_A.ORDER_ITEMS, (ids["line"],))]


async def test_targets_are_locked_in_the_lock_order() -> None:
    world = FakeWorld()
    ids = _delivered_made_line(world)
    reconciler, _ = _reconciler(world)
    reconciler.touch_order_items([ids["line"]])

    await reconciler.run(ACTOR, NOW)

    assert world.lock_log == [
        (_A.LOTS, (ids["lot"],)),
        (_A.ORDERS, (ids["order"],)),
        (_A.ORDER_ITEMS, (ids["line"],)),
        (_A.MADE_DEMANDS, (ids["demand"],)),
    ]


async def test_a_target_added_while_the_first_locks_are_taken_is_locked_and_written() -> None:
    world = FakeWorld()
    order = world.order(status=OrderStatus.ORDERED, ordered_date=NOW)
    line = world.line(order, status=OrderItemStatus.ORDERED, ordered_date=NOW, delivered=10.0)
    late = world.bought_demand(status=BoughtItemDemandStatus.ALLOCATED)

    def concurrent_allocation() -> None:
        world.allocate_bought(late, line, 10.0)

    world.on_first_lock = concurrent_allocation
    reconciler, _ = _reconciler(world)
    reconciler.touch_order_items([line.id])

    await reconciler.run(ACTOR, NOW)

    assert late.id in world.locked(_A.BOUGHT_DEMANDS)
    assert world.bought_demands[late.id].status == "fulfilled"


async def test_a_late_target_sorting_before_a_held_demand_is_locked_late_and_written() -> None:
    world = FakeWorld()
    early = world.bought_demand(quantity=5.0, status=BoughtItemDemandStatus.ALLOCATED)
    order = world.order(status=OrderStatus.ORDERED, ordered_date=NOW)
    line = world.line(order, status=OrderItemStatus.ORDERED, ordered_date=NOW, delivered=10.0)
    held = world.bought_demand(quantity=5.0, status=BoughtItemDemandStatus.ALLOCATED)
    world.allocate_bought(held, line, 5.0)

    def concurrent_allocation() -> None:
        world.allocate_bought(early, line, 5.0)

    world.on_first_lock = concurrent_allocation
    reconciler, _ = _reconciler(world)
    reconciler.touch_order_items([line.id])

    await reconciler.run(ACTOR, NOW)

    assert early.id < held.id
    assert world.lock_log[-2:] == [
        (_A.BOUGHT_DEMANDS, (held.id,)),
        (_A.BOUGHT_DEMANDS, (early.id,)),
    ]
    assert world.bought_demands[early.id].status == "fulfilled"


async def test_status_changes_publish_the_events_their_consumers_read() -> None:
    world = FakeWorld()
    ids = _delivered_made_line(world)
    reconciler, bus = _reconciler(world)
    reconciler.touch_order_items([ids["line"]])

    await reconciler.run(ACTOR, NOW)

    line, position, lot, completed, order, made = bus.published
    assert line == OrderItemStatusChanged(
        order_item_id=ids["line"],
        order_id=ids["order"],
        line_type=OrderLineType.MADE,
        lot_position_id=ids["position"],
        old_status=OrderItemStatus.ORDERED,
        new_status=OrderItemStatus.DELIVERED,
        actor_id=ACTOR.id,
    )
    assert position == LotPositionStatusChanged(
        lot_id=ids["lot"],
        position_id=ids["position"],
        old_status=LotPositionStatus.ORDERED_OR_QUEUED,
        new_status=LotPositionStatus.COMPLETED,
        actor_id=ACTOR.id,
    )
    assert lot == LotStatusChanged(
        lot_id=ids["lot"],
        lot_number="LOT-1",
        creator_id=7,
        old_status=LotStatus.PLANNED,
        new_status=LotStatus.COMPLETED,
        actor_id=ACTOR.id,
    )
    assert completed == LotCompleted(
        lot_id=ids["lot"], lot_number="LOT-1", creator_id=7, made_item_id=3
    )
    assert order == OrderStatusChanged(
        order_id=ids["order"],
        order_number=f"ORD-{ids['order']}",
        supplier_id=2,
        creator_id=7,
        old_status=OrderStatus.ORDERED,
        new_status=OrderStatus.DELIVERED,
        actor_id=ACTOR.id,
    )
    assert isinstance(made, MadeItemDemandItemStatusChanged)
    assert (made.demand_id, made.old_status, made.new_status, made.actor_id) == (
        ids["demand"],
        "ordered",
        "fulfilled",
        ACTOR.id,
    )
    [timeline] = world.lot_events
    assert (timeline.lot_id, timeline.event_type, timeline.summary) == (
        ids["lot"],
        LotEventType.LOT_COMPLETED,
        "Lot completed.",
    )


async def test_production_orders_publish_completed_and_canceled() -> None:
    world = FakeWorld()
    lot = world.lot()
    position = world.position(lot, kind=LotPositionKind.INTERNAL)
    done = world.production_order(
        position, status=ProductionOrderStatus.IN_PROGRESS, actual_start=NOW, processed=10.0
    )
    dropped = world.production_order(position, status=ProductionOrderStatus.QUEUED, canceled_at=NOW)
    reconciler, bus = _reconciler(world)
    reconciler.touch_production_orders([done.id, dropped.id])

    result = await reconciler.run(ACTOR, NOW)

    assert ProductionOrderCompleted(production_order_id=done.id, machine_id=4, creator_id=8) in (
        bus.published
    )
    assert (
        ProductionOrderCanceled(production_order_id=dropped.id, actor_id=ACTOR.id, creator_id=8)
        in bus.published
    )
    assert world.production_orders[done.id].actual_end == NOW
    assert result.schedule_relevant
    assert result.changed_ids(_A.PRODUCTION_ORDERS) == {done.id, dropped.id}


async def test_a_bought_demand_fulfilled_by_a_touched_line_names_that_line() -> None:
    world = FakeWorld()
    order = world.order(status=OrderStatus.ORDERED, ordered_date=NOW)
    line = world.line(order, status=OrderItemStatus.ORDERED, ordered_date=NOW, delivered=10.0)
    demand = world.bought_demand(status=BoughtItemDemandStatus.ORDERED)
    world.allocate_bought(demand, line, 10.0)
    reconciler, bus = _reconciler(world)
    reconciler.touch_order_items([line.id])

    await reconciler.run(ACTOR, NOW)

    [event] = [e for e in bus.published if isinstance(e, DemandItemStatusChanged)]
    assert (event.new_status, event.order_id, event.order_item_id) == (
        BoughtItemDemandStatus.FULFILLED,
        order.id,
        line.id,
    )
    assert (event.item_article_name, event.notify_on_delivery, event.creator_id) == (
        "Bolt",
        True,
        9,
    )


async def test_a_source_demand_publishes_its_status_event() -> None:
    world = FakeWorld()
    order = world.order(status=OrderStatus.ORDERED, ordered_date=NOW)
    line = world.line(order, status=OrderItemStatus.ORDERED, ordered_date=NOW, delivered=10.0)
    demand = world.source_demand(status=SourceItemDemandStatus.ORDERED)
    world.allocate_source(demand, line, 10.0)
    reconciler, bus = _reconciler(world)
    reconciler.touch_order_items([line.id])

    result = await reconciler.run(ACTOR, NOW)

    assert {c.aggregate for c in result.changes} == {_A.ORDER_ITEMS, _A.ORDERS, _A.SOURCE_DEMANDS}
    assert [type(e) for e in bus.published] == [
        OrderItemStatusChanged,
        OrderStatusChanged,
        SourceItemDemandStatusChanged,
    ]
    event = bus.published[-1]
    assert (event.demand_id, event.lot_id, event.old_status, event.new_status) == (
        demand.id,
        demand.lot_id,
        SourceItemDemandStatus.ORDERED,
        SourceItemDemandStatus.FULFILLED,
    )
    assert not result.schedule_relevant


async def test_the_stored_completed_count_is_capped_at_the_position_quantity() -> None:
    world = FakeWorld()
    lot = world.lot(quantity=10.0, status=LotStatus.IN_PROGRESS)
    position = world.position(
        lot, kind=LotPositionKind.INTERNAL, status=LotPositionStatus.PARTIALLY_COMPLETED
    )
    order = world.production_order(
        position, status=ProductionOrderStatus.IN_PROGRESS, actual_start=NOW, processed=12.0
    )
    reconciler, _ = _reconciler(world)
    reconciler.touch_production_orders([order.id])

    await reconciler.run(ACTOR, NOW)

    assert world.positions[position.id].quantity_completed == 10.0


async def test_touch_demands_takes_a_demand_family_only() -> None:
    reconciler, _ = _reconciler(FakeWorld())

    with pytest.raises(ValueError):
        reconciler.touch_demands(_A.LOTS, [1])


def test_an_aggregate_is_reconciled_only_together_with_what_it_reads() -> None:
    with pytest.raises(ValueError, match="orders reads order_items"):
        assert_reconcilable({_A.ORDERS})
    with pytest.raises(ValueError):
        assert_reconcilable({_A.LOTS, _A.LOT_POSITIONS})
    with pytest.raises(ValueError):
        LifecycleReconciler(FakeWorld().repositories, FakeEventBus(), aggregates={_A.MADE_DEMANDS})
    assert_reconcilable(ALL)
    assert_reconcilable({_A.ORDER_ITEMS, _A.ORDERS, _A.BOUGHT_DEMANDS, _A.SOURCE_DEMANDS})


async def test_a_line_locked_first_makes_run_refuse_to_lock_its_order_after_it() -> None:
    world = FakeWorld()
    order = world.order(status=OrderStatus.ORDERED, ordered_date=NOW)
    line = world.line(order, status=OrderItemStatus.ORDERED, ordered_date=NOW, delivered=10.0)
    plan = LockPlan(world.repositories)
    reconciler = LifecycleReconciler(
        world.repositories, FakeEventBus(), aggregates={_A.ORDER_ITEMS, _A.ORDERS}, lock_plan=plan
    )
    # The use case locked its line through the request's plan before anything else.
    await plan.acquire(AggregateIds.of({_A.ORDER_ITEMS: [line.id]}))
    reconciler.touch_order_items([line.id])

    with pytest.raises(LockOrderError):
        await reconciler.run(ACTOR, NOW)

    assert world.locked(_A.ORDERS) == set()
    assert world.saves == []


async def test_lock_touched_first_takes_every_lock_in_one_ordered_acquisition() -> None:
    world = FakeWorld()
    lot = world.lot()
    order = world.order(status=OrderStatus.ORDERED, ordered_date=NOW)
    line = world.line(order, status=OrderItemStatus.ORDERED, ordered_date=NOW, delivered=10.0)
    plan = LockPlan(world.repositories)
    reconciler = LifecycleReconciler(
        world.repositories, FakeEventBus(), aggregates={_A.ORDER_ITEMS, _A.ORDERS}, lock_plan=plan
    )
    reconciler.touch_order_items([line.id])

    await reconciler.lock_touched(also=AggregateIds.of({_A.LOTS: [lot.id]}))
    # The use case's own lock on its line is already held, so nothing is taken.
    await plan.acquire(AggregateIds.of({_A.ORDER_ITEMS: [line.id]}))
    result = await reconciler.run(ACTOR, NOW)

    assert world.lock_log == [
        (_A.LOTS, (lot.id,)),
        (_A.ORDERS, (order.id,)),
        (_A.ORDER_ITEMS, (line.id,)),
    ]
    assert {(c.aggregate, c.new) for c in result.changes if c.field is LifecycleField.STATUS} == {
        (_A.ORDER_ITEMS, "delivered"),
        (_A.ORDERS, "delivered"),
    }


async def test_lock_touched_locks_a_target_added_while_its_locks_are_taken() -> None:
    # A demand that sorts before the held one is allocated to the line while
    # lock_touched waits for its locks. The use case reads what it checks
    # after lock_touched, so that demand must be locked by then, and run
    # must not refuse it as a lock taken out of order.
    world = FakeWorld()
    early = world.bought_demand(quantity=5.0, status=BoughtItemDemandStatus.ALLOCATED)
    order = world.order(status=OrderStatus.ORDERED, ordered_date=NOW)
    line = world.line(order, status=OrderItemStatus.ORDERED, ordered_date=NOW, delivered=10.0)
    held = world.bought_demand(quantity=5.0, status=BoughtItemDemandStatus.ALLOCATED)
    world.allocate_bought(held, line, 5.0)

    def concurrent_allocation() -> None:
        world.allocate_bought(early, line, 5.0)

    world.on_first_lock = concurrent_allocation
    plan = LockPlan(world.repositories)
    reconciler = LifecycleReconciler(world.repositories, FakeEventBus(), lock_plan=plan)
    reconciler.touch_order_items([line.id])

    await reconciler.lock_touched()

    assert early.id < held.id
    assert early.id in world.locked(_A.BOUGHT_DEMANDS)

    await reconciler.run(ACTOR, NOW)

    assert world.bought_demands[early.id].status == "fulfilled"


async def test_lock_touched_with_nothing_reconciled_locks_only_what_it_is_given() -> None:
    world = FakeWorld()
    lot = world.lot()
    line = world.line(world.order())
    reconciler, _ = _reconciler(world, frozenset())
    reconciler.touch_order_items([line.id])

    await reconciler.lock_touched(also=AggregateIds.of({_A.LOTS: [lot.id]}))

    assert world.lock_log == [(_A.LOTS, (lot.id,))]
    assert world.reads == 0


async def test_lock_touched_takes_rows_given_besides_in_the_same_ordered_acquisition() -> None:
    world = FakeWorld()
    demand = world.bought_demand()
    order = world.order(status=OrderStatus.ORDERED, ordered_date=NOW)
    line = world.line(order, status=OrderItemStatus.ORDERED, ordered_date=NOW)
    reconciler, _ = _reconciler(world, frozenset({_A.ORDER_ITEMS, _A.ORDERS}))
    reconciler.touch_order_items([line.id])

    await reconciler.lock_touched(also=AggregateIds.of({_A.BOUGHT_DEMANDS: [demand.id]}))

    assert world.lock_log == [
        (_A.ORDERS, (order.id,)),
        (_A.ORDER_ITEMS, (line.id,)),
        (_A.BOUGHT_DEMANDS, (demand.id,)),
    ]


async def _line_added_after_its_order_and_demand_were_locked(
    world: FakeWorld, *, created: bool
) -> tuple[LifecycleReconciler, dict[str, int]]:
    """A use case that locks an order and a demand, then adds a line on the
    order for the demand, as creating an order line from demands does."""
    order = world.order(status=OrderStatus.ORDERED, ordered_date=NOW)
    demand = world.bought_demand(status=BoughtItemDemandStatus.OPEN)
    reconciler, _ = _reconciler(world, frozenset({_A.ORDER_ITEMS, _A.ORDERS, _A.BOUGHT_DEMANDS}))
    reconciler.touch_orders([order.id])
    reconciler.touch_demands(_A.BOUGHT_DEMANDS, [demand.id])
    await reconciler.lock_touched()
    line = world.line(order, status=OrderItemStatus.ORDERED, ordered_date=NOW)
    world.allocate_bought(demand, line, 10.0)
    reconciler.touch_order_items([line.id], created=created)
    return reconciler, {"order": order.id, "demand": demand.id, "line": line.id}


async def test_a_line_added_after_its_demand_was_locked_is_refused_as_an_existing_row() -> None:
    world = FakeWorld()
    reconciler, ids = await _line_added_after_its_order_and_demand_were_locked(world, created=False)

    with pytest.raises(
        LockOrderError, match=f"order_items #{ids['line']} after bought_demands #{ids['demand']}"
    ):
        await reconciler.run(ACTOR, NOW)


async def test_a_line_the_use_case_created_is_held_without_a_lock_and_written() -> None:
    world = FakeWorld()
    reconciler, ids = await _line_added_after_its_order_and_demand_were_locked(world, created=True)

    await reconciler.run(ACTOR, NOW)

    assert world.lock_log == [(_A.ORDERS, (ids["order"],)), (_A.BOUGHT_DEMANDS, (ids["demand"],))]
    assert world.bought_demands[ids["demand"]].status == "ordered"


async def test_every_touch_records_the_rows_it_created_in_the_lock_plan() -> None:
    world = FakeWorld()
    reconciler, _ = _reconciler(world)

    reconciler.touch_lots([1], created=True)
    reconciler.touch_positions([2], created=True)
    reconciler.touch_production_orders([3], created=True)
    reconciler.touch_orders([4], created=True)
    reconciler.touch_order_items([5], created=True)
    for family, row_id in zip(DEMAND_AGGREGATES, (6, 7, 8), strict=True):
        reconciler.touch_demands(family, [row_id], created=True)
    reconciler.touch_orders([9])

    # A position is held through its lot, so the plan lists none.
    assert reconciler.lock_plan.held == AggregateIds.of(
        {
            _A.LOTS: [1],
            _A.PRODUCTION_ORDERS: [3],
            _A.ORDERS: [4],
            _A.ORDER_ITEMS: [5],
            _A.BOUGHT_DEMANDS: [6],
            _A.MADE_DEMANDS: [7],
            _A.SOURCE_DEMANDS: [8],
        }
    )
    assert world.lock_log == []
