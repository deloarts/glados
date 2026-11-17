"""
Archives a fabrication method, hiding it from pickers for new steps while leaving existing
references to it untouched. An archived method cannot stay the default for assemblies, so
archiving the current default clears that flag and leaves no default set.
"""

from src.modules.catalogue.application.dto.fabrication_method_dto import FabricationMethodResult
from src.modules.catalogue.application.mappers.fabrication_method_mapper import (
    FabricationMethodMapper,
)
from src.modules.catalogue.application.services.labeled_entity_crud import archive_labeled_entity
from src.modules.catalogue.application.use_cases.fabrication_method._spec import SPEC
from src.modules.catalogue.ports.outbound.repositories.fabrication_method_repository import (
    IFabricationMethodRepository,
)
from src.modules.platform.domain.entities.user import User
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork
from src.shared_kernel.domain.services.changelog_service import append_changelog


class ArchiveFabricationMethod:
    def __init__(
        self,
        fabrication_method_repo: IFabricationMethodRepository,
        *,
        uow: IUnitOfWork,
    ) -> None:
        self._fabrication_methods = fabrication_method_repo
        self._uow = uow

    async def execute(self, actor: User, fabrication_method_id: int) -> FabricationMethodResult:
        saved = await archive_labeled_entity(
            SPEC, self._fabrication_methods, actor, fabrication_method_id
        )
        if saved.default_for_assemblies:
            saved.default_for_assemblies = False
            saved.changes = append_changelog(
                saved.changes, actor.full_name, "No longer the default for assemblies."
            )
            saved = await self._fabrication_methods.save(saved)
        await self._uow.commit()
        return FabricationMethodMapper.to_result(saved)
