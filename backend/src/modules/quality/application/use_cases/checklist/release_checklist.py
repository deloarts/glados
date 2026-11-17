"""
Releases a checklist (a second person's sign-off that makes it read-only
for good) and marks a released revision invalid. Releasing a later revision
supersedes the one before it. A release is never taken back: a revision
found to be wrong is marked invalid with a reason, which needs
manage:checklists, and corrected by a new revision.
"""

from src.modules.platform.domain.entities.user import User
from src.modules.platform.ports.outbound.event_bus_port import IEventBus
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork
from src.modules.quality.application.dto.checklist_dto import ChecklistResult
from src.modules.quality.application.dto.checklist_dto import ChecklistSummaryResult
from src.modules.quality.application.dto.controlled_document_dto import MarkInvalidCommand
from src.modules.quality.application.use_cases._controlled_documents.base import (
    MarkControlledDocumentInvalid,
)
from src.modules.quality.application.use_cases._controlled_documents.base import (
    ReleaseControlledDocument,
)
from src.modules.quality.application.use_cases.checklist._kind import KIND
from src.modules.quality.domain.entities.checklist import Checklist
from src.modules.quality.ports.outbound.repositories.checklist_repository import (
    IChecklistRepository,
)


class ReleaseChecklist(
    ReleaseControlledDocument[Checklist, ChecklistResult, ChecklistSummaryResult]
):
    _kind = KIND

    def __init__(self, checklist_repo: IChecklistRepository, *, uow: IUnitOfWork) -> None:
        super().__init__(checklist_repo, uow=uow)

    async def execute(self, actor: User, checklist_id: int) -> ChecklistResult:
        return await self._release(actor, checklist_id)


class MarkChecklistInvalid(
    MarkControlledDocumentInvalid[Checklist, ChecklistResult, ChecklistSummaryResult]
):
    _kind = KIND

    def __init__(
        self, checklist_repo: IChecklistRepository, event_bus: IEventBus, *, uow: IUnitOfWork
    ) -> None:
        super().__init__(checklist_repo, event_bus, uow=uow)

    async def execute(
        self, actor: User, checklist_id: int, cmd: MarkInvalidCommand
    ) -> ChecklistResult:
        return await self._mark_invalid(actor, checklist_id, cmd)
