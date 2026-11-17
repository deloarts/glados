"""
LifecycleLoader.widen: the touched aggregates plus their dependents, along
the edges where a derived value reads another aggregate only. An order item
adds its order, its position and the demands on it; a production order its
position; a position its lot; a lot its positions and the made demands on
it. Orders and demands add nothing, and nothing widens downward.
"""

from src.modules.fulfillment.application.services.lifecycle_loader import AggregateIds
from src.modules.fulfillment.application.services.lifecycle_loader import LifecycleLoader
from src.modules.fulfillment.domain.value_objects.lifecycle_aggregate import DEPENDENTS
from src.modules.fulfillment.domain.value_objects.lifecycle_aggregate import LifecycleAggregate
from src.modules.fulfillment.domain.value_objects.order_status import OrderStatus
from tests.unit.lifecycle.fake_world import NOW
from tests.unit.lifecycle.fake_world import FakeWorld

_A = LifecycleAggregate


async def _widen(world: FakeWorld, touched: dict[LifecycleAggregate, list[int]]) -> AggregateIds:
    return await LifecycleLoader(world.repositories, refresh=True).widen(AggregateIds.of(touched))


def _as_dict(ids: AggregateIds) -> dict[LifecycleAggregate, set[int]]:
    return {aggregate: set(row_ids) for aggregate, row_ids in ids}


def test_the_dependents_follow_the_derivation_edges() -> None:
    expected = {
        _A.ORDER_ITEMS: frozenset(
            {_A.ORDERS, _A.LOT_POSITIONS, _A.BOUGHT_DEMANDS, _A.SOURCE_DEMANDS, _A.QUOTE_REQUESTS}
        ),
        _A.ORDERS: frozenset(),
        _A.PRODUCTION_ORDERS: frozenset({_A.LOT_POSITIONS}),
        _A.LOT_POSITIONS: frozenset({_A.LOTS}),
        _A.LOTS: frozenset({_A.LOT_POSITIONS, _A.MADE_DEMANDS}),
        _A.BOUGHT_DEMANDS: frozenset(),
        _A.MADE_DEMANDS: frozenset(),
        _A.SOURCE_DEMANDS: frozenset(),
        _A.QUOTE_REQUESTS: frozenset(),
    }

    assert expected == DEPENDENTS


async def test_a_made_line_widens_to_its_order_lot_and_every_demand_it_feeds() -> None:
    world = FakeWorld()
    lot = world.lot()
    first = world.position(lot)
    second = world.position(lot)
    order = world.order(status=OrderStatus.ORDERED, ordered_date=NOW)
    line = world.line(order, position=first)
    bought = world.bought_demand()
    world.allocate_bought(bought, line, 2.0)
    source = world.source_demand()
    world.allocate_source(source, line, 3.0)
    made = world.made_demand()
    world.allocate_made(made, lot, 5.0)

    targets = await _widen(world, {_A.ORDER_ITEMS: [line.id]})

    assert _as_dict(targets) == {
        _A.ORDER_ITEMS: {line.id},
        _A.ORDERS: {order.id},
        _A.LOT_POSITIONS: {first.id, second.id},
        _A.LOTS: {lot.id},
        _A.BOUGHT_DEMANDS: {bought.id},
        _A.SOURCE_DEMANDS: {source.id},
        _A.MADE_DEMANDS: {made.id},
    }


async def test_a_line_on_a_shared_order_leaves_the_other_lines_and_their_lots_alone() -> None:
    world = FakeWorld()
    lot = world.lot()
    other_lot = world.lot()
    position = world.position(lot)
    other_position = world.position(other_lot)
    order = world.order(status=OrderStatus.ORDERED, ordered_date=NOW)
    line = world.line(order, position=position)
    other_line = world.line(order, position=other_position)

    targets = await _widen(world, {_A.ORDER_ITEMS: [line.id]})

    assert other_line.id not in targets.get(_A.ORDER_ITEMS)
    assert other_lot.id not in targets.get(_A.LOTS)
    assert other_position.id not in targets.get(_A.LOT_POSITIONS)
    assert targets.get(_A.ORDERS) == {order.id}


async def test_a_production_order_widens_to_its_position_and_lot() -> None:
    world = FakeWorld()
    lot = world.lot()
    position = world.position(lot)
    sibling = world.position(lot)
    production_order = world.production_order(position)
    unrelated = world.production_order(sibling)

    targets = await _widen(world, {_A.PRODUCTION_ORDERS: [production_order.id]})

    assert _as_dict(targets) == {
        _A.PRODUCTION_ORDERS: {production_order.id},
        _A.LOT_POSITIONS: {position.id, sibling.id},
        _A.LOTS: {lot.id},
    }
    assert unrelated.id not in targets.get(_A.PRODUCTION_ORDERS)


async def test_a_touched_position_widens_to_its_lot_and_the_lots_positions() -> None:
    world = FakeWorld()
    lot = world.lot()
    position = world.position(lot)
    sibling = world.position(lot)

    targets = await _widen(world, {_A.LOT_POSITIONS: [position.id]})

    assert _as_dict(targets) == {_A.LOT_POSITIONS: {position.id, sibling.id}, _A.LOTS: {lot.id}}


async def test_a_lot_does_not_widen_to_its_lines_production_orders_or_input_demand() -> None:
    world = FakeWorld()
    input_demand = world.source_demand()
    lot = world.lot(input_demand_id=input_demand.id)
    position = world.position(lot)
    world.production_order(position)
    world.line(world.order(), position=position)

    targets = await _widen(world, {_A.LOTS: [lot.id]})

    assert _as_dict(targets) == {_A.LOTS: {lot.id}, _A.LOT_POSITIONS: {position.id}}


async def test_orders_and_demands_widen_to_nothing() -> None:
    world = FakeWorld()
    order = world.order()
    world.line(order)
    demand = world.bought_demand()
    world.allocate_bought(demand, world.line(world.order()), 1.0)

    targets = await _widen(world, {_A.ORDERS: [order.id], _A.BOUGHT_DEMANDS: [demand.id]})

    assert _as_dict(targets) == {_A.ORDERS: {order.id}, _A.BOUGHT_DEMANDS: {demand.id}}


async def test_unknown_ids_stay_targets_without_widening() -> None:
    world = FakeWorld()

    targets = await _widen(world, {_A.ORDER_ITEMS: [999], _A.LOT_POSITIONS: [998]})

    assert _as_dict(targets) == {_A.ORDER_ITEMS: {999}, _A.LOT_POSITIONS: {998}}
