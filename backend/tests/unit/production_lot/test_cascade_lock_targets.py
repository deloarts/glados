"""
cascade_lock_targets locks what a cascade over a lot's positions may write:
the live production orders and the live lines with their orders. A
completed or canceled production order is never written by a cascade, so it
stays out of the acquisition.
"""

from src.modules.fulfillment.application.services.lot_cascades import cascade_lock_targets
from src.modules.fulfillment.domain.value_objects.lifecycle_aggregate import LifecycleAggregate
from src.modules.fulfillment.domain.value_objects.production_status import ProductionOrderStatus
from tests.unit.production_lot.fakes import FakeOrderItemRepository
from tests.unit.production_lot.fakes import FakeProductionOrderRepository
from tests.unit.production_order._helpers import make_order
from tests.unit.production_order._helpers import make_position


async def test_only_the_live_production_orders_of_the_positions_are_locked() -> None:
    orders = FakeProductionOrderRepository(
        [
            make_order(1, lot_position_id=1, status=ProductionOrderStatus.QUEUED),
            make_order(2, lot_position_id=1, status=ProductionOrderStatus.COMPLETED),
            make_order(3, lot_position_id=2, status=ProductionOrderStatus.CANCELED),
            make_order(4, lot_position_id=2, status=ProductionOrderStatus.PAUSED),
            make_order(5, lot_position_id=3, status=ProductionOrderStatus.QUEUED),
        ]
    )

    targets = await cascade_lock_targets(
        [make_position(1), make_position(2)], orders, FakeOrderItemRepository()
    )

    assert targets.get(LifecycleAggregate.PRODUCTION_ORDERS) == {1, 4}
