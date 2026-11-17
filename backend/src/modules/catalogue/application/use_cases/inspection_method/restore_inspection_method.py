"""
Bespoke (not the shared labeled_entity_crud helper): raises
LabelTranslationConflictError (409) if another live row already holds this
method's name in one of its languages, the same guard restore_labeled_entity
applies.
"""

from src.modules.catalogue.application.dto.inspection_method_dto import InspectionMethodResult
from src.modules.catalogue.application.mappers.inspection_method_mapper import (
    InspectionMethodMapper,
)
from src.modules.catalogue.application.services.labeled_entity_crud import assert_no_name_clash
from src.modules.catalogue.application.services.labeled_entity_crud import shown_name
from src.modules.catalogue.application.use_cases.inspection_method._spec import SPEC
from src.modules.catalogue.domain.entities.inspection_method import InspectionMethod
from src.modules.catalogue.domain.errors import InspectionMethodNotFoundError
from src.modules.catalogue.domain.policies.inspection_method_rules import InspectionMethodRules
from src.modules.catalogue.ports.outbound.repositories.inspection_method_repository import (
    IInspectionMethodRepository,
)
from src.modules.platform.application.services.archive_restore import set_archived
from src.modules.platform.domain.entities.user import User
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork
from src.shared_kernel.domain.services.changelog_service import append_changelog
from src.shared_kernel.domain.services.clock import now_utc


class RestoreInspectionMethod:
    def __init__(
        self,
        inspection_method_repo: IInspectionMethodRepository,
        *,
        uow: IUnitOfWork,
    ) -> None:
        self._inspection_methods = inspection_method_repo
        self._uow = uow

    async def execute(self, actor: User, inspection_method_id: int) -> InspectionMethodResult:
        InspectionMethodRules.assert_can_restore(actor)

        async def _before_save(entity: InspectionMethod) -> None:
            if entity.archived:
                await assert_no_name_clash(SPEC, self._inspection_methods, entity.id, entity.name)

            entity.changed = now_utc()
            entity.changes = append_changelog(
                entity.changes, actor.full_name, "Inspection method restored."
            )

        saved = await set_archived(
            entity_id=inspection_method_id,
            archived=False,
            load=self._inspection_methods.get_by_id,
            not_found=lambda mid: InspectionMethodNotFoundError(
                f"Inspection method #{mid} not found."
            ),
            save=self._inspection_methods.save,
            before_save=_before_save,
        )
        await self._uow.commit()
        log.info(f"Restored inspection method {shown_name(saved.name)!r}, ID={saved.id}.")
        return InspectionMethodMapper.to_result(saved)
