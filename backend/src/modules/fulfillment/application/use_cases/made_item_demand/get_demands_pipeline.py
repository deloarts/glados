"""
Made-item procurement pipeline view (mirrors the bought-item pipeline
view): one row per demand item that is either still in flight
(open/allocated/ordered) or reached a terminal status (fulfilled/canceled)
recently. This view only computes coverage from stock-sourced
allocations, LOT-sourced coverage is left empty here since it isn't
wired into this summary yet (see MadeItemAllocationQuantityService).
"""

from datetime import date

from src.modules.fulfillment.application.dto.made_item_demand_dto import MadeItemPipelineResult
from src.modules.fulfillment.application.dto.made_item_demand_dto import MadeItemPipelineRowResult
from src.modules.fulfillment.domain.entities.made_item_allocation import MadeItemDemandAllocation
from src.modules.fulfillment.domain.entities.made_item_demand_item import MadeItemDemandItem
from src.modules.fulfillment.domain.services.made_item_allocation_service import (
    MadeItemAllocationQuantityService,
)
from src.modules.fulfillment.ports.outbound.repositories.made_item_demand_repository import (
    IMadeItemAllocationRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.made_item_demand_repository import (
    IMadeItemDemandItemRepository,
)


class GetDemandsPipeline:
    def __init__(
        self,
        demand_repo: IMadeItemDemandItemRepository,
        allocation_repo: IMadeItemAllocationRepository,
    ) -> None:
        self._demands = demand_repo
        self._allocations = allocation_repo

    async def execute(self, terminal_since: date) -> MadeItemPipelineResult:
        demands = await self._demands.get_pipeline(terminal_since)
        if not demands:
            return MadeItemPipelineResult(items=[])

        demand_ids = [d.id for d in demands]
        all_allocations = await self._allocations.get_by_demand_item_ids(demand_ids)

        allocations_by_demand: dict[int, list[MadeItemDemandAllocation]] = {
            d.id: [] for d in demands
        }
        for alloc in all_allocations:
            allocations_by_demand.setdefault(alloc.demand_item_id, []).append(alloc)

        rows = [
            self._build_row(demand, allocations_by_demand.get(demand.id, [])) for demand in demands
        ]
        return MadeItemPipelineResult(items=rows)

    def _build_row(
        self,
        demand: MadeItemDemandItem,
        allocations: list[MadeItemDemandAllocation],
    ) -> MadeItemPipelineRowResult:
        # The pipeline reads no lot coverage, so no lot delivers and the fill
        # is empty.
        summary = MadeItemAllocationQuantityService.compute_summary(demand, allocations, fill={})

        return MadeItemPipelineRowResult(
            demand_item_id=demand.id,
            status=demand.status,
            high_priority=demand.high_priority,
            made_item_id=demand.made_item_id,
            item_part_number=demand.item_part_number,
            item_revision=demand.item_revision,
            item_article_name=demand.item_article_name,
            project_id=demand.project_id,
            project_number=demand.project_number,
            unit=demand.unit,
            total=summary.total,
            allocated=summary.allocated,
            ordered=summary.ordered,
            delivered=summary.delivered,
            fulfilled_from_stock=summary.fulfilled_from_stock,
            remaining=summary.remaining,
            is_fully_allocated=summary.is_fully_allocated,
            is_fully_delivered=summary.is_fully_delivered,
        )
