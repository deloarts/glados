"""
The edit lock of a checklist draft: Edit takes it, editing renews it, Discard
or leaving ends it, and it runs out by itself after a while without
activity. Taking the lock needs the same rights as changing the draft;
taking it over from another editor, or ending their editing, needs
manage:checklists, and that editor is notified.
"""

from src.modules.platform.domain.entities.user import User
from src.modules.platform.ports.outbound.event_bus_port import IEventBus
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork
from src.modules.quality.application.dto.checklist_dto import ChecklistResult
from src.modules.quality.application.dto.checklist_dto import ChecklistSummaryResult
from src.modules.quality.application.dto.controlled_document_dto import LockCommand
from src.modules.quality.application.use_cases._controlled_documents.base import (
    LockControlledDocument,
)
from src.modules.quality.application.use_cases._controlled_documents.base import (
    UnlockControlledDocument,
)
from src.modules.quality.application.use_cases.checklist._kind import KIND
from src.modules.quality.domain.entities.checklist import Checklist
from src.modules.quality.ports.outbound.repositories.checklist_repository import (
    IChecklistRepository,
)


class LockChecklist(LockControlledDocument[Checklist, ChecklistResult, ChecklistSummaryResult]):
    _kind = KIND

    def __init__(
        self, checklist_repo: IChecklistRepository, event_bus: IEventBus, *, uow: IUnitOfWork
    ) -> None:
        super().__init__(checklist_repo, event_bus, uow=uow)

    async def execute(self, actor: User, checklist_id: int, cmd: LockCommand) -> ChecklistResult:
        return await self._lock(actor, checklist_id, cmd)


class UnlockChecklist(UnlockControlledDocument[Checklist, ChecklistResult, ChecklistSummaryResult]):
    """Ends the caller's own edit lock, or with `force` someone else's, which
    needs manage:checklists; that editor is notified."""

    _kind = KIND

    def __init__(
        self, checklist_repo: IChecklistRepository, event_bus: IEventBus, *, uow: IUnitOfWork
    ) -> None:
        super().__init__(checklist_repo, event_bus, uow=uow)

    async def execute(
        self, actor: User, checklist_id: int, *, force: bool = False
    ) -> ChecklistResult:
        return await self._unlock(actor, checklist_id, force=force)
