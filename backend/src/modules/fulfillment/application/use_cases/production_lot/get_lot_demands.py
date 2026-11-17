"""Use case for retrieving the made-item demands that a lot was raised to cover."""

from src.modules.fulfillment.application.dto.production_lot_dto import LotDemandResult
from src.modules.fulfillment.application.mappers.production_lot_mapper import LotDemandMapper
from src.modules.fulfillment.domain.errors import LotNotFoundError
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


class GetLotDemands:
    """The made-item demand(s) this lot was raised to cover, the reverse of
    MadeItemDemandAllocation.lot_id, resolved through the allocation join since
    a lot has no direct FK back to a demand."""

    def __init__(
        self,
        lot_repo: IProductionLotRepository,
        made_item_allocation_repo: IMadeItemAllocationRepository,
        made_item_demand_repo: IMadeItemDemandItemRepository,
    ) -> None:
        self._lots = lot_repo
        self._made_item_allocations = made_item_allocation_repo
        self._made_item_demands = made_item_demand_repo

    async def execute(self, lot_id: int) -> list[LotDemandResult]:
        found_or_raise(
            await self._lots.get_by_id(lot_id), LotNotFoundError, f"Lot #{lot_id} not found."
        )

        allocations = await self._made_item_allocations.get_by_lot_id(lot_id)
        if not allocations:
            return []

        demands_by_id = {
            demand.id: demand
            for demand in await self._made_item_demands.get_by_ids(
                [a.demand_item_id for a in allocations]
            )
        }

        results: list[LotDemandResult] = []
        for allocation in allocations:
            demand = demands_by_id.get(allocation.demand_item_id)
            if demand is None:
                continue
            results.append(LotDemandMapper.to_result(demand, allocation.quantity))
        return results
