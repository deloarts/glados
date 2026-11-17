"""
A production order whose stored status is COMPLETED or CANCELED while its
facts say it is live is written back to a live status by the lifecycle
reconciler. Live orders hold their queue places under partial unique
indexes, and a live order of the same queue may hold the revived order's
old place by now, so the reconciler first gives it the next free place of
its queue, under the queue's lock. An order that stays live, or ends, keeps
its place. Runs on the fake world.
"""

from src.modules.fulfillment.application.services.lifecycle_reconciler import LifecycleReconciler
from src.modules.fulfillment.domain.entities.lot_position import LotPosition
from src.modules.fulfillment.domain.entities.production_order import ProductionOrder
from src.modules.fulfillment.domain.value_objects.lifecycle_aggregate import LifecycleAggregate
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionKind
from src.modules.fulfillment.domain.value_objects.production_status import ProductionOrderStatus
from tests.unit.fakes import FakeEventBus
from tests.unit.lifecycle.fake_world import NOW
from tests.unit.lifecycle.fake_world import FakeWorld
from tests.unit.lifecycle.fake_world import actor

_A = LifecycleAggregate


async def _reconcile(world: FakeWorld, order: ProductionOrder) -> ProductionOrder:
    reconciler = LifecycleReconciler(
        world.repositories, FakeEventBus(), aggregates={_A.PRODUCTION_ORDERS}
    )
    reconciler.touch_production_orders([order.id])
    await reconciler.run(actor(), NOW)
    return world.production_orders[order.id]


def _queue(
    world: FakeWorld, *, machine_id: int | None = 4, machine_pool_id: int | None = None
) -> LotPosition:
    """A position with two live orders of one queue at places 1 and 2."""
    position = world.position(world.lot(), kind=LotPositionKind.INTERNAL)
    for place in (1, 2):
        order = world.production_order(
            position, machine_id=machine_id, machine_pool_id=machine_pool_id
        )
        order.queue_sequence = place
    return position


async def test_a_revived_canceled_order_takes_the_next_free_place_of_its_machine():
    world = FakeWorld()
    position = _queue(world)
    # Canceled at place 1 without a cancel intent, so it is live by its facts.
    order = world.production_order(position, status=ProductionOrderStatus.CANCELED)
    order.queue_sequence = 1

    revived = await _reconcile(world, order)

    assert revived.status == "queued"
    assert revived.queue_sequence == 3
    assert world.queue_locks == [(4, None)]


async def test_a_revived_completed_order_of_a_pool_takes_the_pools_next_place():
    world = FakeWorld()
    position = _queue(world, machine_id=None, machine_pool_id=6)
    # Another queue holds higher places, which the pool's queue ignores.
    other = world.production_order(position, machine_id=9)
    other.queue_sequence = 40
    order = world.production_order(
        position,
        status=ProductionOrderStatus.COMPLETED,
        machine_id=None,
        machine_pool_id=6,
        actual_start=NOW,
        processed=4.0,
    )
    order.queue_sequence = 2

    revived = await _reconcile(world, order)

    assert revived.status == "in_progress"
    assert revived.queue_sequence == 3
    assert world.queue_locks == [(None, 6)]


async def test_a_live_order_whose_status_changes_keeps_its_place():
    world = FakeWorld()
    position = _queue(world)
    order = world.production_order(position, status=ProductionOrderStatus.QUEUED, actual_start=NOW)
    order.queue_sequence = 7

    started = await _reconcile(world, order)

    assert started.status == "in_progress"
    assert started.queue_sequence == 7
    assert world.queue_locks == []


async def test_an_order_that_ends_keeps_its_place():
    world = FakeWorld()
    position = _queue(world)
    order = world.production_order(position, status=ProductionOrderStatus.QUEUED, canceled_at=NOW)
    order.queue_sequence = 7

    canceled = await _reconcile(world, order)

    assert canceled.status == "canceled"
    assert canceled.queue_sequence == 7
    assert world.queue_locks == []
