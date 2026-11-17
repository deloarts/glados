"""
Retrieves a source item by ID, or lists source items with optional
filters.
"""

from src.modules.catalogue.application.dto.source_item_dto import SourceItemResult
from src.modules.catalogue.application.mappers.source_item_mapper import SourceItemMapper
from src.modules.catalogue.domain.errors import SourceItemNotFoundError
from src.modules.catalogue.ports.outbound.repositories.source_item_repository import (
    ISourceItemRepository,
)
from src.modules.catalogue.ports.outbound.repositories.source_item_repository import (
    SourceItemFilterDto,
)
from src.modules.platform.application.services.lookup import found_or_raise


class PaginatedSourceItems:
    def __init__(self, total: int, items: list[SourceItemResult]):
        self.total = total
        self.items = items


class GetSourceItem:
    def __init__(self, source_item_repo: ISourceItemRepository) -> None:
        self._items = source_item_repo

    async def execute(self, item_id: int) -> SourceItemResult:
        item = found_or_raise(
            await self._items.get_by_id(item_id),
            SourceItemNotFoundError,
            f"Source item #{item_id} not found.",
        )
        return SourceItemMapper.to_result(item)


class GetSourceItems:
    def __init__(self, source_item_repo: ISourceItemRepository) -> None:
        self._items = source_item_repo

    async def execute(self, filters: SourceItemFilterDto) -> PaginatedSourceItems:
        total, items = await self._items.get_multi(filters)
        return PaginatedSourceItems(
            total=total, items=[SourceItemMapper.to_result(i) for i in items]
        )
