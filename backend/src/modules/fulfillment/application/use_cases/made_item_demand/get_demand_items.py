"""
GetDemandItem and GetDemandItems use cases for retrieving a single demand
item by id and paginated demand item listings.
"""

from src.modules.fulfillment.application.dto.made_item_demand_dto import MadeItemDemandItemResult
from src.modules.fulfillment.application.mappers.made_item_demand_mapper import (
    MadeItemDemandItemMapper,
)
from src.modules.fulfillment.domain.entities.made_item_demand_item import MadeItemDemandItem
from src.modules.fulfillment.domain.errors import DemandItemNotFoundError
from src.modules.fulfillment.ports.outbound.repositories.made_item_demand_repository import (
    IMadeItemDemandItemRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.made_item_demand_repository import (
    MadeItemDemandFilterDto,
)
from src.modules.platform.application.services.lookup import found_or_raise


class PaginatedMadeItemDemandItems:
    def __init__(self, total: int, items: list[MadeItemDemandItemResult]):
        self.total = total
        self.items = items


class GetDemandItem:
    def __init__(self, demand_repo: IMadeItemDemandItemRepository) -> None:
        self._demands = demand_repo

    async def execute(self, demand_id: int) -> MadeItemDemandItemResult:
        return MadeItemDemandItemMapper.to_result(await self._read(demand_id))

    async def changelog(self, demand_id: int) -> list[str]:
        """The demand's changelog lines; a missing id raises
        DemandItemNotFoundError, as execute does."""
        return (await self._read(demand_id)).changes

    async def _read(self, demand_id: int) -> MadeItemDemandItem:
        return found_or_raise(
            await self._demands.get_by_id(demand_id),
            DemandItemNotFoundError,
            f"Demand item #{demand_id} not found.",
        )


class GetDemandItems:
    def __init__(self, demand_repo: IMadeItemDemandItemRepository) -> None:
        self._demands = demand_repo

    async def execute(self, filters: MadeItemDemandFilterDto) -> PaginatedMadeItemDemandItems:
        total, demands = await self._demands.get_multi(filters)
        return PaginatedMadeItemDemandItems(
            total=total, items=[MadeItemDemandItemMapper.to_result(d) for d in demands]
        )
