"""
Retrieves one demand item by ID or lists all demand items with filtering
and pagination.
"""

from src.modules.fulfillment.application.dto.bought_item_demand_dto import DemandItemResult
from src.modules.fulfillment.application.mappers.bought_item_demand_mapper import (
    BoughtItemDemandItemMapper,
)
from src.modules.fulfillment.domain.entities.bought_item_demand_item import BoughtItemDemandItem
from src.modules.fulfillment.domain.errors import DemandItemNotFoundError
from src.modules.fulfillment.ports.outbound.repositories.bought_item_demand_repository import (
    DemandItemFilterDto,
)
from src.modules.fulfillment.ports.outbound.repositories.bought_item_demand_repository import (
    IBoughtItemDemandItemRepository,
)
from src.modules.platform.application.services.lookup import found_or_raise


class PaginatedDemandItems:
    def __init__(self, total: int, items: list[DemandItemResult]):
        self.total = total
        self.items = items


class GetDemandItem:
    def __init__(self, demand_repo: IBoughtItemDemandItemRepository) -> None:
        self._demands = demand_repo

    async def execute(self, demand_id: int) -> DemandItemResult:
        return BoughtItemDemandItemMapper.to_result(await self._read(demand_id))

    async def changelog(self, demand_id: int) -> list[str]:
        """The demand's changelog lines; a missing id raises
        DemandItemNotFoundError, as execute does."""
        return (await self._read(demand_id)).changes

    async def _read(self, demand_id: int) -> BoughtItemDemandItem:
        return found_or_raise(
            await self._demands.get_by_id(demand_id),
            DemandItemNotFoundError,
            f"Demand item #{demand_id} not found.",
        )


class GetDemandItems:
    def __init__(self, demand_repo: IBoughtItemDemandItemRepository) -> None:
        self._demands = demand_repo

    async def execute(self, filters: DemandItemFilterDto) -> PaginatedDemandItems:
        total, demands = await self._demands.get_multi(filters)
        return PaginatedDemandItems(
            total=total, items=[BoughtItemDemandItemMapper.to_result(d) for d in demands]
        )
