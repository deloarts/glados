"""
Creates a new product family via the shared named-entity CRUD service.
"""

from src.modules.catalogue.application.dto.product_family_dto import CreateProductFamilyCommand
from src.modules.catalogue.application.dto.product_family_dto import ProductFamilyResult
from src.modules.catalogue.application.mappers.product_family_mapper import ProductFamilyMapper
from src.modules.catalogue.application.services.named_entity_crud import create_named_entity
from src.modules.catalogue.application.use_cases.product_family._spec import SPEC
from src.modules.catalogue.ports.outbound.repositories.product_family_repository import (
    IProductFamilyRepository,
)
from src.modules.platform.domain.entities.user import User
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork


class CreateProductFamily:
    def __init__(
        self,
        product_family_repo: IProductFamilyRepository,
        *,
        uow: IUnitOfWork,
    ) -> None:
        self._product_families = product_family_repo
        self._uow = uow

    async def execute(self, actor: User, cmd: CreateProductFamilyCommand) -> ProductFamilyResult:
        saved = await create_named_entity(SPEC, self._product_families, actor, cmd)
        await self._uow.commit()
        return ProductFamilyMapper.to_result(saved)
