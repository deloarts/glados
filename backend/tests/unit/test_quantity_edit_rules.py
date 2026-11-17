"""
Unit tests for the quantity edit guards
(src/modules/fulfillment/domain/services/quantity_edit_rules.py). The status a line takes after
its quantity changed is the lifecycle derivation's, tested in
tests/unit/lifecycle/test_derive_order_item.py.
"""

from dataclasses import dataclass
from datetime import UTC
from datetime import datetime

import pytest

from src.modules.fulfillment.domain.entities.order_item import OrderItem
from src.modules.fulfillment.domain.entities.production_lot import ProductionLot
from src.modules.fulfillment.domain.errors import AllocationOverflowError
from src.modules.fulfillment.domain.errors import OrderItemQuantityBelowDeliveredError
from src.modules.fulfillment.domain.services.quantity_edit_rules import (
    assert_demand_quantity_allowed,
)
from src.modules.fulfillment.domain.services.quantity_edit_rules import assert_lot_quantity_allowed
from src.modules.fulfillment.domain.services.quantity_edit_rules import (
    assert_order_item_quantity_allowed,
)
from src.modules.fulfillment.domain.services.quantity_edit_rules import quantity_changed
from src.modules.fulfillment.domain.value_objects.lot_status import LotStatus
from src.modules.fulfillment.domain.value_objects.order_status import OrderItemStatus
from src.modules.fulfillment.domain.value_objects.order_status import OrderLineType
from src.modules.fulfillment.domain.value_objects.production_status import UrgencyClass


def make_line(
    *,
    quantity: float = 10.0,
    delivered: float = 0.0,
    lost: float = 0.0,
    status: OrderItemStatus = OrderItemStatus.ORDERED,
) -> OrderItem:
    return OrderItem(
        id=1,
        created=datetime(2026, 1, 1, tzinfo=UTC),
        changed=None,
        changes=[],
        status=status,
        quantity=quantity,
        quantity_delivered=delivered,
        unit="pcs",
        items_per_unit=1.0,
        price=None,
        note=None,
        ordered_date=None,
        expected_delivery_date=None,
        delivery_date=None,
        storage_place=None,
        expected_pickup_date=None,
        ready_for_pickup_date=None,
        position=1,
        creator_id=1,
        orderer_id=None,
        receiver_id=None,
        bought_item_id=1,
        order_id=1,
        supplier_id=1,
        project_id=1,
        line_type=OrderLineType.BOUGHT,
        lot_position_id=None,
        source_item_id=None,
        quantity_rejected=lost,
        quantity_rejected_lost=lost,
    )


def make_lot(quantity: float = 10.0) -> ProductionLot:
    return ProductionLot(
        id=1,
        created=datetime(2026, 1, 1, tzinfo=UTC),
        changed=None,
        changes=[],
        lot_number="LOT-1",
        quantity=quantity,
        status=LotStatus.DRAFT,
        priority=UrgencyClass.NORMAL,
        note=None,
        creator_id=1,
        made_item_id=1,
        project_id=1,
        input_demand_id=None,
    )


@dataclass
class _Demand:
    id: int
    quantity: float
    unit: str = "pcs"


class TestQuantityChanged:
    def test_float_noise_is_not_a_change(self):
        assert not quantity_changed(10.0, 10.0)
        assert not quantity_changed(10.0, 10.0 + 1e-9)

    def test_a_real_difference_is_a_change(self):
        assert quantity_changed(10.0, 10.001)
        assert quantity_changed(10.0, 9.0)


class TestOrderItemQuantityGuard:
    def test_quantity_below_the_delivered_pieces_is_refused(self):
        # 10 ordered, 6 delivered, then cut to 4.
        line = make_line(quantity=10.0, delivered=6.0)

        with pytest.raises(OrderItemQuantityBelowDeliveredError, match=r"6\.000 pcs delivered"):
            assert_order_item_quantity_allowed(line, 4.0, allocated=0.0)

    def test_lost_pieces_count_as_settled(self):
        line = make_line(quantity=10.0, delivered=4.0, lost=2.0)

        with pytest.raises(OrderItemQuantityBelowDeliveredError):
            assert_order_item_quantity_allowed(line, 5.0, allocated=0.0)
        # This guard returns nothing; reaching the next line is the proof.
        assert_order_item_quantity_allowed(line, 6.0, allocated=0.0)

    def test_quantity_down_to_the_delivered_pieces_is_accepted(self):
        # This guard returns nothing; not raising is the behaviour under test.
        assert_order_item_quantity_allowed(make_line(delivered=6.0), 6.0, allocated=0.0)

    def test_quantity_below_the_allocated_sum_is_refused(self):
        with pytest.raises(AllocationOverflowError, match=r"8\.000 pcs allocated to demands"):
            assert_order_item_quantity_allowed(make_line(), 7.0, allocated=8.0)

    def test_quantity_down_to_the_allocated_sum_is_accepted(self):
        # This guard returns nothing; not raising is the behaviour under test.
        assert_order_item_quantity_allowed(make_line(), 8.0, allocated=8.0)

    def test_float_noise_below_the_delivered_pieces_is_accepted(self):
        # This guard returns nothing; not raising is the behaviour under test.
        assert_order_item_quantity_allowed(make_line(delivered=6.0000004), 6.0, allocated=6.0000004)

    def test_unchanged_quantity_is_accepted_on_a_line_already_below_its_deliveries(self):
        # A row that already breaks the rule must still take an unrelated
        # edit; the forms send the unchanged quantity along with it.
        line = make_line(quantity=4.0, delivered=6.0)

        # This guard returns nothing; not raising is the behaviour under test.
        assert_order_item_quantity_allowed(line, 4.0, allocated=10.0)

    def test_raising_the_quantity_is_accepted(self):
        # This guard returns nothing; not raising is the behaviour under test.
        assert_order_item_quantity_allowed(make_line(delivered=6.0), 12.0, allocated=10.0)


class TestLotQuantityGuard:
    def test_a_lot_cut_below_its_allocations_is_refused(self):
        # A lot of 10 allocated 10 is cut to 5.
        with pytest.raises(AllocationOverflowError, match="allocated to demands"):
            assert_lot_quantity_allowed(make_lot(10.0), 5.0, allocated=10.0)

    def test_a_lot_cut_down_to_its_allocations_is_accepted(self):
        # This guard returns nothing; not raising is the behaviour under test.
        assert_lot_quantity_allowed(make_lot(12.0), 10.0, allocated=10.0)

    def test_raising_a_lot_is_accepted(self):
        # This guard returns nothing; not raising is the behaviour under test.
        assert_lot_quantity_allowed(make_lot(10.0), 15.0, allocated=10.0)

    def test_unchanged_quantity_is_accepted_on_an_over_allocated_lot(self):
        # This guard returns nothing; not raising is the behaviour under test.
        assert_lot_quantity_allowed(make_lot(5.0), 5.0, allocated=10.0)


class TestDemandQuantityGuard:
    def test_a_demand_cut_below_its_allocations_and_stock_is_refused(self):
        with pytest.raises(
            AllocationOverflowError,
            match=r"Demand item #1 has 8\.000 pcs allocated or covered from stock",
        ):
            assert_demand_quantity_allowed(
                _Demand(id=1, quantity=10.0), 7.0, 8.0, noun="Demand item"
            )

    def test_a_demand_cut_down_to_its_coverage_is_accepted(self):
        # This guard returns nothing; not raising is the behaviour under test.
        assert_demand_quantity_allowed(_Demand(id=1, quantity=10.0), 8.0, 8.0, noun="Demand item")

    def test_unchanged_quantity_is_accepted_on_an_over_allocated_demand(self):
        # This guard returns nothing; not raising is the behaviour under test.
        assert_demand_quantity_allowed(_Demand(id=1, quantity=5.0), 5.0, 8.0, noun="Demand item")
