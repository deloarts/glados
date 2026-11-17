"""
Starts a new revision of a finished checklist. The new revision copies the
header, answers and remarks of the latest one, so a revision only needs the
items that changed to be checked again, and takes the next revision string
in the scheme of the admin settings (numeric or letters, with or without
the ambiguous letters). The previous revision is no longer the latest one
and becomes read-only. For a type with a release step it stays the valid
record until the new revision is released; for a type without one the new
revision takes over at once.
"""

from src.modules.fulfillment.api import IFulfillmentSettingsRepository
from src.modules.platform.domain.entities.user import User
from src.modules.platform.ports.outbound.event_bus_port import IEventBus
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork
from src.modules.quality.application.dto.checklist_dto import ChecklistResult
from src.modules.quality.application.dto.checklist_dto import ChecklistSummaryResult
from src.modules.quality.application.dto.checklist_dto import ReviseChecklistCommand
from src.modules.quality.application.use_cases._controlled_documents.base import (
    ReviseControlledDocument,
)
from src.modules.quality.application.use_cases.checklist._kind import KIND
from src.modules.quality.domain.entities.checklist import Checklist
from src.modules.quality.ports.outbound.repositories.checklist_repository import (
    IChecklistRepository,
)


class ReviseChecklist(ReviseControlledDocument[Checklist, ChecklistResult, ChecklistSummaryResult]):
    _kind = KIND

    def __init__(
        self,
        checklist_repo: IChecklistRepository,
        admin_settings_repo: IFulfillmentSettingsRepository,
        event_bus: IEventBus,
        *,
        uow: IUnitOfWork,
    ) -> None:
        super().__init__(checklist_repo, admin_settings_repo, event_bus, uow=uow)

    async def execute(
        self, actor: User, checklist_id: int, cmd: ReviseChecklistCommand
    ) -> ChecklistResult:
        return await self._revise(actor, checklist_id, cmd.reason)
