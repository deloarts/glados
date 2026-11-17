"""
Lot-backed counterpart of allocation_service.py, the made-item side of
the coverage protocol defined in allocation_coverage.py.

The `lot_coverage` dict is sourced from a ProductionLot repo (see
src.modules.fulfillment.domain.services.lot_rules.build_lot_coverage) and passed in by the
caller, compute_summary's signature stays the same regardless of how
that dict is produced. The demand's status is derived by the lifecycle
reconciler.
"""

from collections.abc import Mapping
from collections.abc import Sequence

from src.modules.catalogue.domain.value_objects.made_item_status import MadeItemAllocationSource
from src.modules.fulfillment.domain.entities.made_item_allocation import MadeItemDemandAllocation
from src.modules.fulfillment.domain.entities.made_item_demand_item import MadeItemDemandItem
from src.modules.fulfillment.domain.services.allocation_coverage import CoverageInfo
from src.modules.fulfillment.domain.services.allocation_coverage import compute_coverage_totals
from src.modules.fulfillment.domain.services.lifecycle.demand import MADE_FILL_RANK
from src.modules.fulfillment.domain.services.lifecycle.demand import FillEntry
from src.modules.fulfillment.domain.value_objects.demand_summary import DemandQuantitySummary


class _LotCoverageSource:
    """Lot-backed coverage adapter for compute_coverage_totals."""

    def __init__(self, lot_coverage: dict[int, CoverageInfo]) -> None:
        self._lot_coverage = lot_coverage

    def coverage_for(self, ref_id: int) -> CoverageInfo | None:
        return self._lot_coverage.get(ref_id)


class MadeItemAllocationQuantityService:
    """
    Computes quantity summaries from raw allocation + lot coverage lists.
    Mirrors AllocationQuantityService, keyed by lot instead of order item.
    """

    @staticmethod
    def compute_summary(
        demand: MadeItemDemandItem,
        allocations: list[MadeItemDemandAllocation],
        lot_coverage: dict[int, CoverageInfo] | None = None,
        *,
        fill: Mapping[int, Sequence[FillEntry]],
    ) -> DemandQuantitySummary:
        allocated, ordered, delivered, fulfilled_from_stock = compute_coverage_totals(
            allocations,
            _LotCoverageSource(lot_coverage or {}),
            MadeItemAllocationSource.STOCK,
            rank=MADE_FILL_RANK,
            fill=fill,
        )

        lot_ids = tuple(sorted({a.lot_id for a in allocations if a.lot_id}))

        return DemandQuantitySummary(
            demand_item_id=demand.id,
            unit=demand.unit,
            total=demand.quantity,
            allocated=allocated,
            ordered=ordered,
            delivered=delivered,
            fulfilled_from_stock=fulfilled_from_stock,
            order_ids=lot_ids,
        )
