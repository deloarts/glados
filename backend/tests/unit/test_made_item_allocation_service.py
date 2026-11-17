"""
Direct unit tests for src/modules/fulfillment/domain/services/made_item_allocation_service.py:
_LotCoverageSource and MadeItemAllocationQuantityService.compute_summary.
Mirrors tests/unit/test_allocation_service.py and
tests/unit/test_source_item_allocation_service.py, this file's production
code is the lot-backed counterpart of the same coverage shape. The demand's
status is derived by domain/services/lifecycle/demand.py, tested in
tests/unit/lifecycle.

made_item_allocation_service.py has no *Rules class of its own (allocation
guards for made items are covered by the application-layer use case tests
in tests/unit/test_made_item_allocation_use_cases.py).
"""

from datetime import date

from src.modules.catalogue.domain.value_objects.made_item_status import MadeItemAllocationSource
from src.modules.catalogue.domain.value_objects.made_item_status import MadeItemDemandStatus
from src.modules.fulfillment.domain.entities.made_item_allocation import MadeItemDemandAllocation
from src.modules.fulfillment.domain.entities.made_item_demand_item import MadeItemDemandItem
from src.modules.fulfillment.domain.services.allocation_coverage import CoverageInfo
from src.modules.fulfillment.domain.services.made_item_allocation_service import (
    MadeItemAllocationQuantityService,
)
from src.modules.fulfillment.domain.services.made_item_allocation_service import _LotCoverageSource

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


# ── _LotCoverageSource ────────────────────────────────────────────────


class TestLotCoverageSource:
    def test_unknown_ref_returns_none(self):
        source = _LotCoverageSource({})
        assert source.coverage_for(999) is None

    def test_known_ref_returns_info(self):
        info = CoverageInfo(is_placed=True, arrived=5.0)
        source = _LotCoverageSource({5: info})
        assert source.coverage_for(5) is info


# ── MadeItemAllocationQuantityService.compute_summary ──────────────────


class TestComputeSummary:
    def test_no_lot_coverage_defaults_ordered_and_delivered_to_zero(self):
        demand = make_demand(quantity=10.0)
        allocations = [
            MadeItemDemandAllocation(
                demand_item_id=1, lot_id=5, quantity=8.0, source=MadeItemAllocationSource.LOT
            ),
            MadeItemDemandAllocation(
                demand_item_id=1, lot_id=None, quantity=2.0, source=MadeItemAllocationSource.STOCK
            ),
        ]

        summary = MadeItemAllocationQuantityService.compute_summary(demand, allocations, fill={})

        assert summary.allocated == 8.0
        assert summary.ordered == 0.0
        assert summary.delivered == 0.0
        assert summary.fulfilled_from_stock == 2.0

    def test_lot_coverage_reflects_the_completed_pieces(self):
        demand = make_demand(quantity=10.0)
        allocations = [
            MadeItemDemandAllocation(
                demand_item_id=1, lot_id=5, quantity=8.0, source=MadeItemAllocationSource.LOT
            ),
        ]
        lot_coverage = {5: CoverageInfo(is_placed=True, arrived=4.0)}

        summary = MadeItemAllocationQuantityService.compute_summary(
            demand, allocations, lot_coverage, fill={}
        )

        assert summary.allocated == 8.0
        assert summary.ordered == 8.0
        assert summary.delivered == 4.0

    def test_lot_ids_excludes_stock_allocations(self):
        demand = make_demand(quantity=10.0)
        allocations = [
            MadeItemDemandAllocation(
                demand_item_id=1, lot_id=5, quantity=8.0, source=MadeItemAllocationSource.LOT
            ),
            MadeItemDemandAllocation(
                demand_item_id=1, lot_id=None, quantity=2.0, source=MadeItemAllocationSource.STOCK
            ),
        ]

        summary = MadeItemAllocationQuantityService.compute_summary(demand, allocations, fill={})

        assert summary.order_ids == (5,)
