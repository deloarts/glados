"""
Retrieves one inspection method by ID, or lists inspection methods with filtering and
pagination.
"""

from src.modules.catalogue.application.dto.inspection_method_dto import InspectionMethodResult
from src.modules.catalogue.application.mappers.inspection_method_mapper import (
    InspectionMethodMapper,
)
from src.modules.catalogue.application.services.labeled_entity_crud import get_labeled_entities
from src.modules.catalogue.application.services.labeled_entity_crud import get_labeled_entity
from src.modules.catalogue.application.use_cases.inspection_method._spec import SPEC
from src.modules.catalogue.ports.outbound.repositories.inspection_method_repository import (
    IInspectionMethodRepository,
)
from src.modules.catalogue.ports.outbound.repositories.inspection_method_repository import (
    InspectionMethodFilterDto,
)


class PaginatedInspectionMethods:
    def __init__(self, total: int, items: list[InspectionMethodResult]):
        self.total = total
        self.items = items


class GetInspectionMethod:
    def __init__(self, inspection_method_repo: IInspectionMethodRepository) -> None:
        self._inspection_methods = inspection_method_repo

    async def execute(self, inspection_method_id: int) -> InspectionMethodResult:
        entity = await get_labeled_entity(SPEC, self._inspection_methods, inspection_method_id)
        return InspectionMethodMapper.to_result(entity)

    async def changelog(self, inspection_method_id: int) -> list[str]:
        """The inspection method's changelog lines; a missing id raises the same
        not-found error as execute."""
        entity = await get_labeled_entity(SPEC, self._inspection_methods, inspection_method_id)
        return entity.changes


class GetInspectionMethods:
    def __init__(self, inspection_method_repo: IInspectionMethodRepository) -> None:
        self._inspection_methods = inspection_method_repo

    async def execute(self, filters: InspectionMethodFilterDto) -> PaginatedInspectionMethods:
        total, items = await get_labeled_entities(self._inspection_methods, filters)
        return PaginatedInspectionMethods(
            total=total, items=[InspectionMethodMapper.to_result(i) for i in items]
        )
