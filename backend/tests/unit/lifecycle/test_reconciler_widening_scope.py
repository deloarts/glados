"""
The lifecycle reconciler widens what a use case touched only inside the
aggregates it writes. A touched production order widens to its position
and lot when every aggregate is written, and to nothing else while only
production orders are: the reconciler then reads, locks and writes
production orders alone. Runs on the fake world.
"""

import dataclasses

from src.modules.fulfillment.application.services.lifecycle_loader import AggregateIds
from src.modules.fulfillment.application.services.lifecycle_loader import LifecycleLoader
from src.modules.fulfillment.application.services.lifecycle_reconciler import LifecycleReconciler
from src.modules.fulfillment.domain.value_objects.lifecycle_aggregate import LifecycleAggregate
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionKind
from src.modules.fulfillment.domain.value_objects.lot_status import LotStatus
from src.modules.fulfillment.domain.value_objects.production_status import ProductionOrderStatus
from tests.unit.fakes import FakeEventBus
from tests.unit.lifecycle.fake_world import NOW
from tests.unit.lifecycle.fake_world import FakeWorld
from tests.unit.lifecycle.fake_world import actor

_A = LifecycleAggregate


class _Untouchable:
    """A repository the reconciler must not use; any call fails the test."""

    def __init__(self, name: str) -> None:
        self._name = name

    def __getattr__(self, method: str):
        async def refuse(*_args: object, **_kwargs: object) -> None:
            raise AssertionError(f"The reconciler called {self._name}.{method}.")

        return refuse


def _started_order(world: FakeWorld) -> int:
    """A production order stored as queued although it has started."""
    position = world.position(world.lot(status=LotStatus.PLANNED), kind=LotPositionKind.INTERNAL)
    return world.production_order(
        position, status=ProductionOrderStatus.QUEUED, actual_start=NOW
    ).id


async def test_widening_follows_the_order_to_its_lot_only_when_both_are_written():
    world = FakeWorld()
    order_id = _started_order(world)
    touched = AggregateIds.of({_A.PRODUCTION_ORDERS: [order_id]})
    loader = LifecycleLoader(world.repositories, refresh=False)

    everything = await loader.widen(touched)
    inside = await loader.widen(touched, within={_A.PRODUCTION_ORDERS})

    assert set(everything.by_aggregate) == {_A.PRODUCTION_ORDERS, _A.LOT_POSITIONS, _A.LOTS}
    assert inside == touched


async def test_a_production_order_reconciler_uses_no_other_repository():
    world = FakeWorld()
    order_id = _started_order(world)
    repositories = dataclasses.replace(
        world.repositories,
        **{
            name: _Untouchable(name)
            for name in (
                "lots",
                "orders",
                "order_items",
                "bought_demands",
                "bought_allocations",
                "made_demands",
                "made_allocations",
                "source_demands",
                "source_allocations",
            )
        },
    )
    reconciler = LifecycleReconciler(
        repositories, FakeEventBus(), aggregates={_A.PRODUCTION_ORDERS}
    )
    reconciler.touch_production_orders([order_id])

    await reconciler.run(actor(), NOW)

    assert world.production_orders[order_id].status == "in_progress"
    assert world.lock_log == [(_A.PRODUCTION_ORDERS, (order_id,))]
