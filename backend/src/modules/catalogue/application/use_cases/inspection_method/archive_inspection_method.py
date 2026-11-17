"""
Bespoke (not the shared labeled_entity_crud helper): blocks archiving the
method currently set as AdminProductionSettings.default_inspection_method_id;
require_qa must never silently point at a method nobody can pick anymore.
"""

from src.modules.catalogue.application.dto.inspection_method_dto import InspectionMethodResult
from src.modules.catalogue.application.mappers.inspection_method_mapper import (
    InspectionMethodMapper,
)
from src.modules.catalogue.application.services.labeled_entity_crud import shown_name
from src.modules.catalogue.domain.entities.inspection_method import InspectionMethod
from src.modules.catalogue.domain.errors import InspectionMethodConfigurationError
from src.modules.catalogue.domain.errors import InspectionMethodNotFoundError
from src.modules.catalogue.domain.policies.inspection_method_rules import InspectionMethodRules
from src.modules.catalogue.ports.outbound.inspection_method_usage_port import IInspectionMethodUsage
from src.modules.catalogue.ports.outbound.repositories.inspection_method_repository import (
    IInspectionMethodRepository,
)
from src.modules.platform.application.services.archive_restore import set_archived
from src.modules.platform.domain.entities.user import User
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork
from src.shared_kernel.domain.services.changelog_service import append_changelog
from src.shared_kernel.domain.services.clock import now_utc


class ArchiveInspectionMethod:
    def __init__(
        self,
        inspection_method_repo: IInspectionMethodRepository,
        settings_repo: IInspectionMethodUsage,
        *,
        uow: IUnitOfWork,
    ) -> None:
        self._inspection_methods = inspection_method_repo
        self._settings = settings_repo
        self._uow = uow

    async def execute(self, actor: User, inspection_method_id: int) -> InspectionMethodResult:
        InspectionMethodRules.assert_can_archive(actor)

        async def _before_save(entity: InspectionMethod) -> None:
            if not entity.archived:
                production = await self._settings.get_production()
                if production.default_inspection_method_id == entity.id:
                    raise InspectionMethodConfigurationError(
                        f"Inspection method {shown_name(entity.name)!r} is the require_qa default and "
                        "cannot be archived - pick a different default first."
                    )

            entity.changed = now_utc()
            entity.changes = append_changelog(
                entity.changes, actor.full_name, "Inspection method archived."
            )

        saved = await set_archived(
            entity_id=inspection_method_id,
            archived=True,
            load=self._inspection_methods.get_by_id,
            not_found=lambda mid: InspectionMethodNotFoundError(
                f"Inspection method #{mid} not found."
            ),
            save=self._inspection_methods.save,
            before_save=_before_save,
        )
        await self._uow.commit()
        log.info(f"Archived inspection method {shown_name(saved.name)!r}, ID={saved.id}.")
        return InspectionMethodMapper.to_result(saved)
