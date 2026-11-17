"""
Retrieves one fabrication method by ID, the default for assemblies, or lists fabrication
methods with filtering and pagination.
"""

from src.modules.catalogue.application.dto.fabrication_method_dto import FabricationMethodResult
from src.modules.catalogue.application.mappers.fabrication_method_mapper import (
    FabricationMethodMapper,
)
from src.modules.catalogue.application.services.labeled_entity_crud import get_labeled_entities
from src.modules.catalogue.application.services.labeled_entity_crud import get_labeled_entity
from src.modules.catalogue.application.use_cases.fabrication_method._spec import SPEC
from src.modules.catalogue.ports.outbound.repositories.fabrication_method_repository import (
    FabricationMethodFilterDto,
)
from src.modules.catalogue.ports.outbound.repositories.fabrication_method_repository import (
    IFabricationMethodRepository,
)


class PaginatedFabricationMethods:
    def __init__(self, total: int, items: list[FabricationMethodResult]):
        self.total = total
        self.items = items


class GetFabricationMethod:
    def __init__(self, fabrication_method_repo: IFabricationMethodRepository) -> None:
        self._fabrication_methods = fabrication_method_repo

    async def execute(self, fabrication_method_id: int) -> FabricationMethodResult:
        entity = await get_labeled_entity(SPEC, self._fabrication_methods, fabrication_method_id)
        return FabricationMethodMapper.to_result(entity)

    async def changelog(self, fabrication_method_id: int) -> list[str]:
        """The fabrication method's changelog lines; a missing id raises the same
        not-found error as execute."""
        entity = await get_labeled_entity(SPEC, self._fabrication_methods, fabrication_method_id)
        return entity.changes


class GetAssemblyDefaultFabricationMethod:
    def __init__(self, fabrication_method_repo: IFabricationMethodRepository) -> None:
        self._fabrication_methods = fabrication_method_repo

    async def execute(self) -> FabricationMethodResult | None:
        """None when no method is the default for assemblies."""
        entity = await self._fabrication_methods.get_default_for_assemblies()
        return FabricationMethodMapper.to_result(entity) if entity else None


class GetFabricationMethods:
    def __init__(self, fabrication_method_repo: IFabricationMethodRepository) -> None:
        self._fabrication_methods = fabrication_method_repo

    async def execute(self, filters: FabricationMethodFilterDto) -> PaginatedFabricationMethods:
        total, items = await get_labeled_entities(self._fabrication_methods, filters)
        return PaginatedFabricationMethods(
            total=total, items=[FabricationMethodMapper.to_result(i) for i in items]
        )
