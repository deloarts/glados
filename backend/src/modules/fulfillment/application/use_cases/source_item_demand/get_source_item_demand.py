"""
Retrieves a source item demand by ID, or lists source item demands with
optional filters.
"""

from src.modules.fulfillment.application.dto.source_item_demand_dto import SourceItemDemandResult
from src.modules.fulfillment.application.mappers.source_item_demand_mapper import (
    SourceItemDemandMapper,
)
from src.modules.fulfillment.domain.errors import SourceItemDemandNotFoundError
from src.modules.fulfillment.ports.outbound.repositories.source_item_demand_repository import (
    ISourceItemDemandRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.source_item_demand_repository import (
    SourceItemDemandFilterDto,
)
from src.modules.platform.application.services.lookup import found_or_raise


class PaginatedSourceItemDemands:
    def __init__(self, total: int, items: list[SourceItemDemandResult]):
        self.total = total
        self.items = items


class GetSourceItemDemand:
    def __init__(self, demand_repo: ISourceItemDemandRepository) -> None:
        self._demands = demand_repo

    async def execute(self, demand_id: int) -> SourceItemDemandResult:
        demand = found_or_raise(
            await self._demands.get_by_id(demand_id),
            SourceItemDemandNotFoundError,
            f"Source item demand #{demand_id} not found.",
        )
        return SourceItemDemandMapper.to_result(demand)


class GetSourceItemDemands:
    def __init__(self, demand_repo: ISourceItemDemandRepository) -> None:
        self._demands = demand_repo

    async def execute(self, filters: SourceItemDemandFilterDto) -> PaginatedSourceItemDemands:
        total, items = await self._demands.get_multi(filters)
        return PaginatedSourceItemDemands(
            total=total, items=[SourceItemDemandMapper.to_result(i) for i in items]
        )
