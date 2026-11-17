"""
Restores an archived fabrication method, making it selectable again for new steps.
"""

from src.modules.catalogue.application.dto.fabrication_method_dto import FabricationMethodResult
from src.modules.catalogue.application.mappers.fabrication_method_mapper import (
    FabricationMethodMapper,
)
from src.modules.catalogue.application.services.labeled_entity_crud import restore_labeled_entity
from src.modules.catalogue.application.use_cases.fabrication_method._spec import SPEC
from src.modules.catalogue.ports.outbound.repositories.fabrication_method_repository import (
    IFabricationMethodRepository,
)
from src.modules.platform.domain.entities.user import User
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork


class RestoreFabricationMethod:
    def __init__(
        self,
        fabrication_method_repo: IFabricationMethodRepository,
        *,
        uow: IUnitOfWork,
    ) -> None:
        self._fabrication_methods = fabrication_method_repo
        self._uow = uow

    async def execute(self, actor: User, fabrication_method_id: int) -> FabricationMethodResult:
        saved = await restore_labeled_entity(
            SPEC, self._fabrication_methods, actor, fabrication_method_id
        )
        await self._uow.commit()
        return FabricationMethodMapper.to_result(saved)
