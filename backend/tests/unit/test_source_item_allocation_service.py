"""
Direct unit tests for src/modules/fulfillment/domain/services/source_item_allocation_service.py:
OrderItemCoverageSource, SourceItemAllocationQuantityService.compute_summary
and SourceItemAllocationRules. The demand's status is derived by
domain/services/lifecycle/demand.py, tested in tests/unit/lifecycle.
Mirrors tests/unit/test_allocation_service.py, this file's production code
is the source-item counterpart of allocation_service.py's bought-item logic.
"""

from datetime import date

import pytest

from src.modules.fulfillment.domain.entities.order_item import OrderItem
from src.modules.fulfillment.domain.entities.source_item_demand_item import SourceItemDemandItem
from src.modules.fulfillment.domain.errors import AllocationItemMismatchError
from src.modules.fulfillment.domain.errors import AllocationOverflowError
from src.modules.fulfillment.domain.errors import SourceItemDemandAlreadyCanceledError
from src.modules.fulfillment.domain.errors import SourceItemDemandAlreadyFulfilledError
from src.modules.fulfillment.domain.services.allocation_coverage import OrderItemCoverageSource
from src.modules.fulfillment.domain.services.source_item_allocation_service import (
    SourceItemAllocationRules,
)
from src.modules.fulfillment.domain.value_objects.order_status import OrderItemStatus
from src.modules.fulfillment.domain.value_objects.order_status import OrderLineType
from src.modules.fulfillment.domain.value_objects.source_item_demand_status import (
    SourceItemDemandStatus,
)
from src.modules.platform.domain.exceptions import InsufficientPermissionsError
from src.modules.platform.domain.value_objects.permission import Permission
from tests.factories import make_user

# ── Helpers ───────────────────────────────────────────────────────────


def make_order_item(
    id: int = 1,
    quantity: float = 10.0,
    quantity_delivered: float = 0.0,
    status: OrderItemStatus = OrderItemStatus.ORDERED,
    bought_item_id: int | None = 1,
    source_item_id: int | None = None,
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
        line_type=OrderLineType.SOURCE if source_item_id else OrderLineType.BOUGHT,
        lot_position_id=None,
        source_item_id=source_item_id,
    )


def make_demand(
    id: int = 1,
    quantity: float = 10.0,
    status: SourceItemDemandStatus = SourceItemDemandStatus.ALLOCATED,
    bought_item_id: int | None = 1,
    source_item_id: int | None = None,
) -> SourceItemDemandItem:
    return SourceItemDemandItem(
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
        bought_item_id=bought_item_id,
        source_item_id=source_item_id,
        lot_id=1,
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


# ── SourceItemAllocationRules ───────────────────────────────────────────


class TestSourceItemAllocationRules:
    def test_assert_can_allocate_with_permission(self):
        actor = make_user(permissions=[Permission.WRITE_ALLOCATIONS])
        SourceItemAllocationRules.assert_can_allocate(actor)

    def test_assert_can_allocate_without_permission_raises(self):
        actor = make_user(permissions=[])
        with pytest.raises(InsufficientPermissionsError):
            SourceItemAllocationRules.assert_can_allocate(actor)

    def test_assert_not_terminal_fulfilled_raises(self):
        demand = make_demand(status=SourceItemDemandStatus.FULFILLED)
        with pytest.raises(SourceItemDemandAlreadyFulfilledError):
            SourceItemAllocationRules.assert_not_terminal(demand)

    def test_assert_not_terminal_canceled_raises(self):
        demand = make_demand(status=SourceItemDemandStatus.CANCELED)
        with pytest.raises(SourceItemDemandAlreadyCanceledError):
            SourceItemAllocationRules.assert_not_terminal(demand)

    def test_assert_not_terminal_open_does_not_raise(self):
        demand = make_demand(status=SourceItemDemandStatus.OPEN)
        SourceItemAllocationRules.assert_not_terminal(demand)

    def test_assert_no_overallocation_within_bounds(self):
        demand = make_demand(quantity=10.0)
        SourceItemAllocationRules.assert_no_overallocation(
            demand, existing_allocated=5.0, new_quantity=3.0
        )

    def test_assert_no_overallocation_exceeds_raises(self):
        demand = make_demand(quantity=10.0)
        with pytest.raises(AllocationOverflowError):
            SourceItemAllocationRules.assert_no_overallocation(
                demand, existing_allocated=8.0, new_quantity=5.0
            )

    def test_assert_no_overallocation_exact_boundary_does_not_raise(self):
        demand = make_demand(quantity=10.0)
        SourceItemAllocationRules.assert_no_overallocation(
            demand, existing_allocated=5.0, new_quantity=5.0
        )

    def test_assert_no_overallocation_with_exclude_existing(self):
        demand = make_demand(quantity=10.0)
        SourceItemAllocationRules.assert_no_overallocation(
            demand, existing_allocated=5.0, new_quantity=8.0, exclude_existing=5.0
        )

    def test_assert_material_matches_bought_item_match(self):
        demand = make_demand(bought_item_id=1, source_item_id=None)
        order_item = make_order_item(bought_item_id=1)
        SourceItemAllocationRules.assert_material_matches(demand, order_item)

    def test_assert_material_matches_bought_item_mismatch_raises(self):
        demand = make_demand(bought_item_id=1, source_item_id=None)
        order_item = make_order_item(bought_item_id=2)
        with pytest.raises(AllocationItemMismatchError):
            SourceItemAllocationRules.assert_material_matches(demand, order_item)

    def test_assert_material_matches_source_item_match(self):
        demand = make_demand(bought_item_id=None, source_item_id=2)
        order_item = make_order_item(bought_item_id=None, source_item_id=2)
        SourceItemAllocationRules.assert_material_matches(demand, order_item)

    def test_assert_material_matches_source_item_mismatch_raises(self):
        demand = make_demand(bought_item_id=None, source_item_id=2)
        order_item = make_order_item(bought_item_id=None, source_item_id=3)
        with pytest.raises(AllocationItemMismatchError):
            SourceItemAllocationRules.assert_material_matches(demand, order_item)

    def test_assert_material_matches_neither_source_set_raises(self):
        demand = make_demand(bought_item_id=None, source_item_id=None)
        order_item = make_order_item(bought_item_id=1)
        with pytest.raises(AllocationItemMismatchError):
            SourceItemAllocationRules.assert_material_matches(demand, order_item)

    # ── Substitution ─────────────────────────────────────────────────

    def test_assert_material_matches_substitute_equal_to_order_line_accepted(self):
        """A source-sourced demand may be allocated to a different order
        line when the caller declares substitute_source_item_id, provided
        it equals that order line's own source_item_id (the caller's
        acknowledgement, mirrors BoughtItemAllocationRules.assert_bought_item_matches)."""
        demand = make_demand(bought_item_id=None, source_item_id=2)
        order_item = make_order_item(bought_item_id=None, source_item_id=3)
        SourceItemAllocationRules.assert_material_matches(
            demand, order_item, substitute_source_item_id=3
        )

    def test_assert_material_matches_substitute_different_from_order_line_raises(self):
        """The substitute id must equal the order line's own source_item_id,
        not just any value the caller sends."""
        demand = make_demand(bought_item_id=None, source_item_id=2)
        order_item = make_order_item(bought_item_id=None, source_item_id=3)
        with pytest.raises(AllocationItemMismatchError):
            SourceItemAllocationRules.assert_material_matches(
                demand, order_item, substitute_source_item_id=4
            )

    def test_assert_material_matches_substitute_rejected_for_bought_sourced_demand(self):
        """Bought-item-sourced demands stay non-substitutable: passing
        substitute_source_item_id never waives a bought_item_id mismatch."""
        demand = make_demand(bought_item_id=1, source_item_id=None)
        order_item = make_order_item(bought_item_id=2, source_item_id=None)
        with pytest.raises(AllocationItemMismatchError):
            SourceItemAllocationRules.assert_material_matches(
                demand, order_item, substitute_source_item_id=2
            )

    def test_assert_material_matches_substitute_rejected_when_order_line_is_bought(self):
        """A source-sourced demand cannot substitute onto a BOUGHT order
        line: substitution is source-items-only."""
        demand = make_demand(bought_item_id=None, source_item_id=2)
        order_item = make_order_item(bought_item_id=7, source_item_id=None)
        with pytest.raises(AllocationItemMismatchError):
            SourceItemAllocationRules.assert_material_matches(
                demand, order_item, substitute_source_item_id=7
            )
