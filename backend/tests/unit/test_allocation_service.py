"""
Direct unit tests for src/modules/fulfillment/domain/services/allocation_service.py:
OrderItemCoverageSource and BoughtItemAllocationRules. The demand's status
is derived by domain/services/lifecycle/demand.py, tested in
tests/unit/lifecycle.

The happy-path proportional-delivery cases of
AllocationQuantityService.compute_summary are already covered in
tests/unit/test_bought_item_delivery.py and are not duplicated here.
"""

from datetime import date

import pytest

from src.modules.catalogue.domain.value_objects.bought_item_status import BoughtItemDemandStatus
from src.modules.fulfillment.domain.entities.bought_item_demand_item import BoughtItemDemandItem
from src.modules.fulfillment.domain.entities.order_item import OrderItem
from src.modules.fulfillment.domain.errors import AllocationItemMismatchError
from src.modules.fulfillment.domain.errors import AllocationOverflowError
from src.modules.fulfillment.domain.errors import DemandItemAlreadyCanceledError
from src.modules.fulfillment.domain.errors import DemandItemAlreadyFulfilledError
from src.modules.fulfillment.domain.services.allocation_coverage import OrderItemCoverageSource
from src.modules.fulfillment.domain.services.allocation_service import BoughtItemAllocationRules
from src.modules.fulfillment.domain.value_objects.order_status import OrderItemStatus
from src.modules.fulfillment.domain.value_objects.order_status import OrderLineType
from src.modules.platform.domain.exceptions import InsufficientPermissionsError
from src.modules.platform.domain.value_objects.permission import Permission
from tests.factories import make_user

# ── Helpers ───────────────────────────────────────────────────────────


def make_order_item(
    id: int = 1,
    quantity: float = 10.0,
    quantity_delivered: float = 0.0,
    status: OrderItemStatus = OrderItemStatus.ORDERED,
    bought_item_id: int = 1,
) -> OrderItem:
    return OrderItem(
        id=id,
        created=date(2026, 1, 1),
        changed=None,
        changes=[],
        status=status,
        quantity=quantity,
        quantity_delivered=quantity_delivered,
        unit="pcs",
        items_per_unit=1.0,
        price=None,
        note=None,
        ordered_date=date(2026, 1, 1),
        expected_delivery_date=None,
        delivery_date=None,
        storage_place=None,
        expected_pickup_date=None,
        ready_for_pickup_date=None,
        position=1,
        creator_id=1,
        orderer_id=None,
        receiver_id=None,
        bought_item_id=bought_item_id,
        order_id=1,
        supplier_id=1,
        project_id=1,
        line_type=OrderLineType.BOUGHT,
        lot_position_id=None,
        source_item_id=None,
    )


def make_demand(
    id: int = 1,
    quantity: float = 10.0,
    status: BoughtItemDemandStatus = BoughtItemDemandStatus.ALLOCATED,
    item_id: int = 1,
) -> BoughtItemDemandItem:
    return BoughtItemDemandItem(
        id=id,
        created=date(2026, 1, 1),
        changed=None,
        changes=[],
        status=status,
        quantity=quantity,
        unit="pcs",
        items_per_unit=1.0,
        high_priority=False,
        notify_on_delivery=False,
        note=None,
        desired_delivery_date=None,
        creator_id=1,
        item_id=item_id,
        project_id=1,
    )


# ── OrderItemCoverageSource ──────────────────────────────────────────


class TestOrderItemCoverageSource:
    def test_unknown_ref_returns_none(self):
        source = OrderItemCoverageSource({})
        assert source.coverage_for(999) is None

    def test_placed_order_item_reports_its_accepted_pieces(self):
        order_item = make_order_item(
            id=1, quantity=10.0, quantity_delivered=4.0, status=OrderItemStatus.ORDERED
        )
        source = OrderItemCoverageSource({1: order_item})
        info = source.coverage_for(1)
        assert info is not None
        assert info.is_placed is True
        assert info.arrived == 4.0

    def test_pending_order_item_is_not_placed(self):
        order_item = make_order_item(id=1, status=OrderItemStatus.PENDING)
        source = OrderItemCoverageSource({1: order_item})
        info = source.coverage_for(1)
        assert info is not None
        assert info.is_placed is False

    def test_zero_quantity_order_item_has_nothing_arrived(self):
        order_item = make_order_item(id=1, quantity=0.0, quantity_delivered=0.0)
        source = OrderItemCoverageSource({1: order_item})
        info = source.coverage_for(1)
        assert info is not None
        assert info.arrived == 0.0


# ── BoughtItemAllocationRules ────────────────────────────────────────


class TestBoughtItemAllocationRules:
    def test_assert_can_allocate_with_permission(self):
        actor = make_user(permissions=[Permission.WRITE_ALLOCATIONS])
        BoughtItemAllocationRules.assert_can_allocate(actor)

    def test_assert_can_allocate_without_permission_raises(self):
        actor = make_user(permissions=[])
        with pytest.raises(InsufficientPermissionsError):
            BoughtItemAllocationRules.assert_can_allocate(actor)

    def test_assert_not_terminal_fulfilled_raises(self):
        demand = make_demand(status=BoughtItemDemandStatus.FULFILLED)
        with pytest.raises(DemandItemAlreadyFulfilledError):
            BoughtItemAllocationRules.assert_not_terminal(demand)

    def test_assert_not_terminal_canceled_raises(self):
        demand = make_demand(status=BoughtItemDemandStatus.CANCELED)
        with pytest.raises(DemandItemAlreadyCanceledError):
            BoughtItemAllocationRules.assert_not_terminal(demand)

    def test_assert_not_terminal_open_does_not_raise(self):
        demand = make_demand(status=BoughtItemDemandStatus.OPEN)
        BoughtItemAllocationRules.assert_not_terminal(demand)

    def test_assert_no_overallocation_within_bounds(self):
        demand = make_demand(quantity=10.0)
        BoughtItemAllocationRules.assert_no_overallocation(
            demand, existing_allocated=5.0, new_quantity=3.0
        )

    def test_assert_no_overallocation_exceeds_raises(self):
        demand = make_demand(quantity=10.0)
        with pytest.raises(AllocationOverflowError):
            BoughtItemAllocationRules.assert_no_overallocation(
                demand, existing_allocated=8.0, new_quantity=5.0
            )

    def test_assert_no_overallocation_exact_boundary_does_not_raise(self):
        demand = make_demand(quantity=10.0)
        BoughtItemAllocationRules.assert_no_overallocation(
            demand, existing_allocated=5.0, new_quantity=5.0
        )

    def test_assert_no_overallocation_with_exclude_existing(self):
        demand = make_demand(quantity=10.0)
        # Replacing an existing 5.0 allocation with a new 8.0 one, net
        # effect is 8.0, within bounds.
        BoughtItemAllocationRules.assert_no_overallocation(
            demand, existing_allocated=5.0, new_quantity=8.0, exclude_existing=5.0
        )

    def test_assert_bought_item_matches_same_item(self):
        demand = make_demand(item_id=1)
        order_item = make_order_item(bought_item_id=1)
        BoughtItemAllocationRules.assert_bought_item_matches(demand, order_item)

    def test_assert_bought_item_matches_mismatch_raises(self):
        demand = make_demand(item_id=1)
        order_item = make_order_item(bought_item_id=2)
        with pytest.raises(AllocationItemMismatchError):
            BoughtItemAllocationRules.assert_bought_item_matches(demand, order_item)

    def test_assert_bought_item_matches_valid_substitution(self):
        demand = make_demand(item_id=1)
        order_item = make_order_item(bought_item_id=2)
        BoughtItemAllocationRules.assert_bought_item_matches(
            demand, order_item, substitute_item_id=2
        )

    def test_assert_bought_item_matches_wrong_substitute_raises(self):
        demand = make_demand(item_id=1)
        order_item = make_order_item(bought_item_id=2)
        with pytest.raises(AllocationItemMismatchError):
            BoughtItemAllocationRules.assert_bought_item_matches(
                demand, order_item, substitute_item_id=3
            )
