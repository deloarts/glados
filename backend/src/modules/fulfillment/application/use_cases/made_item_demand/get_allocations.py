"""
Retrieves per-demand allocation summaries, combining allocation rows with
lot coverage to report how much of each demand is covered.
"""

from src.modules.fulfillment.application.dto.made_item_allocation_dto import (
    MadeItemAllocationResult,
)
from src.modules.fulfillment.application.dto.made_item_allocation_dto import (
    MadeItemDemandSummaryResult,
)
from src.modules.fulfillment.application.mappers.made_item_allocation_mapper import (
    MadeItemAllocationMapper,
)
from src.modules.fulfillment.application.services.allocation_fill import lot_fill
from src.modules.fulfillment.domain.entities.made_item_allocation import MadeItemDemandAllocation
from src.modules.fulfillment.domain.errors import DemandItemNotFoundError
from src.modules.fulfillment.domain.services.allocation_coverage import CoverageInfo
from src.modules.fulfillment.domain.services.lot_rules import build_lot_coverage
from src.modules.fulfillment.domain.services.made_item_allocation_service import (
    MadeItemAllocationQuantityService,
)
from src.modules.fulfillment.ports.outbound.repositories.made_item_demand_repository import (
    IMadeItemAllocationRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.made_item_demand_repository import (
    IMadeItemDemandItemRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.production_lot_repository import (
    IProductionLotRepository,
)
from src.modules.platform.application.services.lookup import found_or_raise


async def _lot_coverage_for(
    allocations: list[MadeItemDemandAllocation], lot_repo: IProductionLotRepository
) -> dict[int, CoverageInfo]:
    lot_ids = sorted({a.lot_id for a in allocations if a.lot_id})
    return build_lot_coverage(await lot_repo.get_by_ids(lot_ids)) if lot_ids else {}


class GetAllocationsForDemand:
    """Returns all allocations for a demand item."""

    def __init__(self, allocation_repo: IMadeItemAllocationRepository) -> None:
        self._allocations = allocation_repo

    async def execute(self, demand_item_id: int) -> list[MadeItemAllocationResult]:
        allocations = await self._allocations.get_by_demand_item_id(demand_item_id)
        return [MadeItemAllocationMapper.to_result(a) for a in allocations]


class GetDemandSummary:
    """
    Computes the full quantity breakdown for a demand item:
    total, allocated, delivered, remaining, unallocated, in_transit.
    """

    def __init__(
        self,
        demand_repo: IMadeItemDemandItemRepository,
        allocation_repo: IMadeItemAllocationRepository,
        lot_repo: IProductionLotRepository,
    ) -> None:
        self._demands = demand_repo
        self._allocations = allocation_repo
        self._lots = lot_repo

    async def execute(self, demand_item_id: int) -> MadeItemDemandSummaryResult:
        demand = found_or_raise(
            await self._demands.get_by_id(demand_item_id),
            DemandItemNotFoundError,
            f"Demand item #{demand_item_id} not found.",
        )

        allocations = await self._allocations.get_by_demand_item_id(demand_item_id)
        lot_coverage = await _lot_coverage_for(allocations, self._lots)
        fill = await lot_fill(lot_coverage, self._allocations)
        summary = MadeItemAllocationQuantityService.compute_summary(
            demand, allocations, lot_coverage, fill=fill
        )

        return MadeItemDemandSummaryResult(
            demand_item_id=summary.demand_item_id,
            unit=summary.unit,
            total=summary.total,
            allocated=summary.allocated,
            fulfilled_from_stock=summary.fulfilled_from_stock,
            ordered=summary.ordered,
            delivered=summary.delivered,
            remaining=summary.remaining,
            unallocated=summary.unallocated,
            pending=summary.pending,
            in_transit=summary.in_transit,
            is_fully_allocated=summary.is_fully_allocated,
            is_fully_delivered=summary.is_fully_delivered,
            lot_ids=list(summary.order_ids),
        )


class GetDemandSummaryBatch:
    """
    Computes quantity summaries for multiple demand items in one call.
    Used by list views to show remaining quantity per row without N+1 queries.
    """

    def __init__(
        self,
        demand_repo: IMadeItemDemandItemRepository,
        allocation_repo: IMadeItemAllocationRepository,
        lot_repo: IProductionLotRepository,
    ) -> None:
        self._demands = demand_repo
        self._allocations = allocation_repo
        self._lots = lot_repo

    async def execute(self, demand_item_ids: list[int]) -> dict[int, MadeItemDemandSummaryResult]:
        results: dict[int, MadeItemDemandSummaryResult] = {}

        all_allocations = await self._allocations.get_by_demand_item_ids(demand_item_ids)
        allocations_by_demand: dict[int, list[MadeItemDemandAllocation]] = {}
        for allocation in all_allocations:
            allocations_by_demand.setdefault(allocation.demand_item_id, []).append(allocation)

        lot_coverage = await _lot_coverage_for(all_allocations, self._lots)
        fill = await lot_fill(lot_coverage, self._allocations)
        # Batched: one get_by_ids call for the whole demand_item_ids list
        # instead of per-demand get_by_id calls (avoids N+1 queries).
        demands_by_id = {d.id: d for d in await self._demands.get_by_ids(demand_item_ids)}

        for demand_id in demand_item_ids:
            demand = demands_by_id.get(demand_id)
            if not demand:
                continue

            allocations = allocations_by_demand.get(demand_id, [])
            summary = MadeItemAllocationQuantityService.compute_summary(
                demand, allocations, lot_coverage, fill=fill
            )

            results[demand_id] = MadeItemDemandSummaryResult(
                demand_item_id=summary.demand_item_id,
                unit=summary.unit,
                total=summary.total,
                allocated=summary.allocated,
                fulfilled_from_stock=summary.fulfilled_from_stock,
                ordered=summary.ordered,
                delivered=summary.delivered,
                remaining=summary.remaining,
                unallocated=summary.unallocated,
                pending=summary.pending,
                in_transit=summary.in_transit,
                is_fully_allocated=summary.is_fully_allocated,
                is_fully_delivered=summary.is_fully_delivered,
                lot_ids=list(summary.order_ids),
            )

        return results
