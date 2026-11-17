"""
Retrieves a source item type by ID, or lists source item types with
optional filters, using shared labeled-entity logic.
"""

from src.modules.catalogue.application.dto.source_item_type_dto import SourceItemTypeResult
from src.modules.catalogue.application.mappers.source_item_type_mapper import SourceItemTypeMapper
from src.modules.catalogue.application.services.labeled_entity_crud import get_labeled_entities
from src.modules.catalogue.application.services.labeled_entity_crud import get_labeled_entity
from src.modules.catalogue.application.use_cases.source_item_type._spec import SPEC
from src.modules.catalogue.ports.outbound.repositories.source_item_type_repository import (
    ISourceItemTypeRepository,
)
from src.modules.catalogue.ports.outbound.repositories.source_item_type_repository import (
    SourceItemTypeFilterDto,
)


class PaginatedSourceItemTypes:
    def __init__(self, total: int, items: list[SourceItemTypeResult]):
        self.total = total
        self.items = items


class GetSourceItemType:
    def __init__(self, source_item_type_repo: ISourceItemTypeRepository) -> None:
        self._source_item_types = source_item_type_repo

    async def execute(self, source_item_type_id: int) -> SourceItemTypeResult:
        entity = await get_labeled_entity(SPEC, self._source_item_types, source_item_type_id)
        return SourceItemTypeMapper.to_result(entity)

    async def changelog(self, source_item_type_id: int) -> list[str]:
        """The source item type's changelog lines; a missing id raises the same
        not-found error as execute."""
        entity = await get_labeled_entity(SPEC, self._source_item_types, source_item_type_id)
        return entity.changes


class GetSourceItemTypes:
    def __init__(self, source_item_type_repo: ISourceItemTypeRepository) -> None:
        self._source_item_types = source_item_type_repo

    async def execute(self, filters: SourceItemTypeFilterDto) -> PaginatedSourceItemTypes:
        total, items = await get_labeled_entities(self._source_item_types, filters)
        return PaginatedSourceItemTypes(
            total=total, items=[SourceItemTypeMapper.to_result(i) for i in items]
        )
