"""
LockPlan takes row locks in the one lock order: lots, production orders,
orders, order items, bought, made and source demands, ascending ids within
each. It never locks a row twice, refuses a row that sorts before one it
already locked, and locks late only through acquire_late. Rows the
transaction created count as held without a lock and without the order
check.
"""

import pytest

from src.modules.fulfillment.application.services.lifecycle_loader import AggregateIds
from src.modules.fulfillment.application.services.lifecycle_lock_plan import LOCK_ORDER
from src.modules.fulfillment.application.services.lifecycle_lock_plan import LockOrderError
from src.modules.fulfillment.application.services.lifecycle_lock_plan import LockPlan
from src.modules.fulfillment.domain.value_objects.lifecycle_aggregate import LifecycleAggregate
from tests.unit.lifecycle.fake_world import FakeWorld

_A = LifecycleAggregate


async def test_locks_follow_the_one_lock_order_with_ascending_ids() -> None:
    world = FakeWorld()
    plan = LockPlan(world.repositories)

    await plan.acquire(
        AggregateIds.of(
            {
                _A.SOURCE_DEMANDS: [7],
                _A.ORDER_ITEMS: [9, 3],
                _A.LOTS: [5, 2],
                _A.BOUGHT_DEMANDS: [4],
                _A.ORDERS: [8],
                _A.MADE_DEMANDS: [6],
                _A.PRODUCTION_ORDERS: [11, 1],
                _A.QUOTE_REQUESTS: [13, 12],
            }
        )
    )

    assert world.lock_log == [
        (_A.LOTS, (2, 5)),
        (_A.PRODUCTION_ORDERS, (1, 11)),
        (_A.ORDERS, (8,)),
        (_A.ORDER_ITEMS, (3, 9)),
        (_A.BOUGHT_DEMANDS, (4,)),
        (_A.MADE_DEMANDS, (6,)),
        (_A.SOURCE_DEMANDS, (7,)),
        (_A.QUOTE_REQUESTS, (12, 13)),
    ]
    assert tuple(aggregate for aggregate, _ in world.lock_log) == LOCK_ORDER


async def test_a_later_acquisition_in_order_locks_only_rows_not_held_yet() -> None:
    world = FakeWorld()
    plan = LockPlan(world.repositories)
    await plan.acquire(AggregateIds.of({_A.LOTS: [1, 2], _A.ORDERS: [5]}))

    await plan.acquire(AggregateIds.of({_A.LOTS: [2], _A.ORDERS: [5, 7], _A.ORDER_ITEMS: [3]}))

    assert world.lock_log == [
        (_A.LOTS, (1, 2)),
        (_A.ORDERS, (5,)),
        (_A.ORDERS, (7,)),
        (_A.ORDER_ITEMS, (3,)),
    ]
    assert plan.held.get(_A.ORDERS) == {5, 7}


async def test_an_order_after_a_held_line_is_refused() -> None:
    world = FakeWorld()
    plan = LockPlan(world.repositories)
    await plan.acquire(AggregateIds.of({_A.ORDER_ITEMS: [4]}))

    with pytest.raises(LockOrderError, match="orders #2 after order_items #4"):
        await plan.acquire(AggregateIds.of({_A.ORDERS: [2], _A.ORDER_ITEMS: [4]}))

    assert world.lock_log == [(_A.ORDER_ITEMS, (4,))]
    assert plan.held.get(_A.ORDERS) == frozenset()


async def test_a_lower_id_after_a_higher_one_of_the_same_aggregate_is_refused() -> None:
    world = FakeWorld()
    plan = LockPlan(world.repositories)
    await plan.acquire(AggregateIds.of({_A.BOUGHT_DEMANDS: [5]}))

    with pytest.raises(LockOrderError):
        await plan.acquire(AggregateIds.of({_A.BOUGHT_DEMANDS: [3]}))


async def test_the_order_is_checked_against_the_last_held_row_not_the_first() -> None:
    world = FakeWorld()
    plan = LockPlan(world.repositories)
    await plan.acquire(AggregateIds.of({_A.LOTS: [1], _A.ORDER_ITEMS: [9]}))

    with pytest.raises(LockOrderError, match="orders #3 after order_items #9"):
        await plan.acquire(AggregateIds.of({_A.ORDERS: [3]}))

    assert world.locked(_A.ORDERS) == set()


async def test_created_rows_count_as_held_without_a_lock_or_the_order_check() -> None:
    world = FakeWorld()
    plan = LockPlan(world.repositories)
    await plan.acquire(AggregateIds.of({_A.ORDERS: [5], _A.BOUGHT_DEMANDS: [8]}))

    # A line sorts before the demand already locked, but nobody else sees it yet.
    plan.record_created(AggregateIds.of({_A.ORDER_ITEMS: [12]}))
    await plan.acquire(AggregateIds.of({_A.ORDERS: [5], _A.ORDER_ITEMS: [12]}))

    assert world.lock_log == [(_A.ORDERS, (5,)), (_A.BOUGHT_DEMANDS, (8,))]
    assert plan.held.get(_A.ORDER_ITEMS) == {12}
    assert AggregateIds.of({_A.ORDERS: [5], _A.ORDER_ITEMS: [12]}).issubset(plan.held)


async def test_created_rows_do_not_raise_the_bar_for_a_later_acquisition() -> None:
    world = FakeWorld()
    plan = LockPlan(world.repositories)
    plan.record_created(AggregateIds.of({_A.SOURCE_DEMANDS: [20]}))

    await plan.acquire(AggregateIds.of({_A.ORDERS: [3], _A.ORDER_ITEMS: [4]}))

    assert world.lock_log == [(_A.ORDERS, (3,)), (_A.ORDER_ITEMS, (4,))]


async def test_a_late_acquisition_locks_out_of_order_rows_in_order_among_themselves() -> None:
    world = FakeWorld()
    plan = LockPlan(world.repositories)
    await plan.acquire(AggregateIds.of({_A.ORDER_ITEMS: [4], _A.BOUGHT_DEMANDS: [9]}))

    await plan.acquire_late(AggregateIds.of({_A.BOUGHT_DEMANDS: [9, 6, 2], _A.ORDERS: [3]}))

    assert world.lock_log[2:] == [(_A.ORDERS, (3,)), (_A.BOUGHT_DEMANDS, (2, 6))]


async def test_positions_are_locked_through_their_lot_and_nothing_locks_for_nothing() -> None:
    world = FakeWorld()
    plan = LockPlan(world.repositories)

    await plan.acquire(AggregateIds.of({_A.LOT_POSITIONS: [4, 5]}))
    await plan.acquire(AggregateIds())

    assert world.lock_log == []
    assert plan.held.is_empty()
