"""
Unit tests for src/modules/fulfillment/domain/services/production_machine_status_rules.py's
pure resolve_machine_status function: all four states and the precedence
between an open downtime and the machine's active orders.
"""

from datetime import date

from src.modules.fulfillment.domain.entities.production_order import ProductionOrder
from src.modules.fulfillment.domain.services.production_machine_status_rules import (
    resolve_machine_status,
)
from src.modules.fulfillment.domain.value_objects.production_machine_status import (
    ProductionMachineStatus,
)
from src.modules.fulfillment.domain.value_objects.production_status import ProductionOrderStatus
from src.modules.fulfillment.domain.value_objects.production_status import UrgencyClass


def _order(status: ProductionOrderStatus) -> ProductionOrder:
    return ProductionOrder(
        id=1,
        created=date(2026, 1, 1),
        changed=None,
        changes=[],
        production_order_number="PO-0001",
        status=status,
        priority=UrgencyClass.NORMAL,
        pinned=False,
        queue_sequence=1,
        quantity=10.0,
        quantity_completed=0.0,
        estimated_duration_minutes=60,
        note=None,
        planned_start=None,
        planned_end=None,
        not_before=None,
        actual_start=None,
        actual_end=None,
        creator_id=1,
        machine_id=1,
        lot_position_id=1,
    )


class TestResolveMachineStatus:
    def test_no_orders_no_downtime_is_idle(self):
        assert resolve_machine_status([], has_open_downtime=False) == ProductionMachineStatus.IDLE

    def test_one_in_progress_order_is_running(self):
        orders = [_order(ProductionOrderStatus.IN_PROGRESS)]
        assert (
            resolve_machine_status(orders, has_open_downtime=False)
            == ProductionMachineStatus.RUNNING
        )

    def test_one_paused_order_is_paused(self):
        orders = [_order(ProductionOrderStatus.PAUSED)]
        assert (
            resolve_machine_status(orders, has_open_downtime=False)
            == ProductionMachineStatus.PAUSED
        )

    def test_open_downtime_is_down_regardless_of_orders(self):
        orders = [_order(ProductionOrderStatus.IN_PROGRESS)]
        assert (
            resolve_machine_status(orders, has_open_downtime=True) == ProductionMachineStatus.DOWN
        )

    def test_open_downtime_beats_paused_orders_too(self):
        orders = [_order(ProductionOrderStatus.PAUSED)]
        assert (
            resolve_machine_status(orders, has_open_downtime=True) == ProductionMachineStatus.DOWN
        )

    def test_in_progress_beats_paused_when_both_present(self):
        orders = [
            _order(ProductionOrderStatus.PAUSED),
            _order(ProductionOrderStatus.IN_PROGRESS),
        ]
        assert (
            resolve_machine_status(orders, has_open_downtime=False)
            == ProductionMachineStatus.RUNNING
        )

    def test_downtime_alone_with_no_orders_is_down(self):
        assert resolve_machine_status([], has_open_downtime=True) == ProductionMachineStatus.DOWN
