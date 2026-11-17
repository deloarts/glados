"""
Retrieves a single product family by ID or lists product families with pagination via the
shared named-entity service.
"""

from src.modules.catalogue.application.dto.product_family_dto import ProductFamilyResult
from src.modules.catalogue.application.mappers.product_family_mapper import ProductFamilyMapper
from src.modules.catalogue.application.services.named_entity_crud import get_named_entities
from src.modules.catalogue.application.services.named_entity_crud import get_named_entity
from src.modules.catalogue.application.use_cases.product_family._spec import SPEC
from src.modules.catalogue.ports.outbound.catalogue_queries import ProductFamilyFilterDto
from src.modules.catalogue.ports.outbound.repositories.product_family_repository import (
    IProductFamilyRepository,
)


class PaginatedProductFamilies:
    def __init__(self, total: int, items: list[ProductFamilyResult]):
        self.total = total
        self.items = items


class GetProductFamily:
    def __init__(self, product_family_repo: IProductFamilyRepository) -> None:
        self._product_families = product_family_repo

    async def execute(self, product_family_id: int) -> ProductFamilyResult:
        entity = await get_named_entity(SPEC, self._product_families, product_family_id)
        return ProductFamilyMapper.to_result(entity)

    async def changelog(self, product_family_id: int) -> list[str]:
        """The product family's changelog lines; a missing id raises the same
        not-found error as execute."""
        entity = await get_named_entity(SPEC, self._product_families, product_family_id)
        return entity.changes


class GetProductFamilies:
    def __init__(self, product_family_repo: IProductFamilyRepository) -> None:
        self._product_families = product_family_repo

    async def execute(self, filters: ProductFamilyFilterDto) -> PaginatedProductFamilies:
        total, items = await get_named_entities(self._product_families, filters)
        return PaginatedProductFamilies(
            total=total, items=[ProductFamilyMapper.to_result(i) for i in items]
        )
