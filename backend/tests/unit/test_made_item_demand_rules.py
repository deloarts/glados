"""
Direct unit tests for src/modules/fulfillment/domain/services/made_item_demand_rules.py's
MadeItemAllocationRules, assert_can_allocate, assert_not_terminal,
assert_no_overallocation. Mirrors tests/unit/test_allocation_service.py's
TestBoughtItemAllocationRules and test_source_item_allocation_service.py's
TestSourceItemAllocationRules, since this class is structurally identical
to those two.
"""

from datetime import date

import pytest

from src.modules.catalogue.domain.value_objects.made_item_status import MadeItemDemandStatus
from src.modules.fulfillment.domain.entities.made_item_demand_item import MadeItemDemandItem
from src.modules.fulfillment.domain.errors import AllocationOverflowError
from src.modules.fulfillment.domain.errors import DemandItemAlreadyCanceledError
from src.modules.fulfillment.domain.errors import DemandItemAlreadyFulfilledError
from src.modules.fulfillment.domain.services.made_item_demand_rules import MadeItemAllocationRules
from src.modules.platform.domain.exceptions import InsufficientPermissionsError
from src.modules.platform.domain.value_objects.permission import Permission
from tests.factories import make_user

# ── Helpers ───────────────────────────────────────────────────────────


def make_demand(
    id: int = 1,
    quantity: float = 10.0,
    status: MadeItemDemandStatus = MadeItemDemandStatus.ALLOCATED,
) -> MadeItemDemandItem:
    return MadeItemDemandItem(
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
        made_item_id=1,
        project_id=1,
    )


# ── MadeItemAllocationRules ───────────────────────────────────────────


class TestMadeItemAllocationRules:
    def test_assert_can_allocate_with_permission(self):
        actor = make_user(permissions=[Permission.WRITE_ALLOCATIONS])
        MadeItemAllocationRules.assert_can_allocate(actor)

    def test_assert_can_allocate_without_permission_raises(self):
        actor = make_user(permissions=[])
        with pytest.raises(InsufficientPermissionsError):
            MadeItemAllocationRules.assert_can_allocate(actor)

    def test_assert_not_terminal_fulfilled_raises(self):
        demand = make_demand(status=MadeItemDemandStatus.FULFILLED)
        with pytest.raises(DemandItemAlreadyFulfilledError):
            MadeItemAllocationRules.assert_not_terminal(demand)

    def test_assert_not_terminal_canceled_raises(self):
        demand = make_demand(status=MadeItemDemandStatus.CANCELED)
        with pytest.raises(DemandItemAlreadyCanceledError):
            MadeItemAllocationRules.assert_not_terminal(demand)

    def test_assert_not_terminal_open_does_not_raise(self):
        demand = make_demand(status=MadeItemDemandStatus.OPEN)
        MadeItemAllocationRules.assert_not_terminal(demand)

    def test_assert_no_overallocation_within_bounds(self):
        demand = make_demand(quantity=10.0)
        MadeItemAllocationRules.assert_no_overallocation(
            demand, existing_allocated=5.0, new_quantity=3.0
        )

    def test_assert_no_overallocation_exceeds_raises(self):
        demand = make_demand(quantity=10.0)
        with pytest.raises(AllocationOverflowError):
            MadeItemAllocationRules.assert_no_overallocation(
                demand, existing_allocated=8.0, new_quantity=5.0
            )

    def test_assert_no_overallocation_exact_boundary_does_not_raise(self):
        demand = make_demand(quantity=10.0)
        MadeItemAllocationRules.assert_no_overallocation(
            demand, existing_allocated=5.0, new_quantity=5.0
        )

    def test_assert_no_overallocation_with_exclude_existing(self):
        demand = make_demand(quantity=10.0)
        MadeItemAllocationRules.assert_no_overallocation(
            demand, existing_allocated=5.0, new_quantity=8.0, exclude_existing=5.0
        )
