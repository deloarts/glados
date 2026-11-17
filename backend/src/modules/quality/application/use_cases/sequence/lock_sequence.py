"""
The edit lock of a sequence draft: Edit takes it, editing renews it, Discard
or leaving ends it, and it runs out by itself after a while without
activity. Taking the lock needs the same rights as changing the draft;
taking it over from another editor, or ending their editing, needs
manage:sequences, and that editor is notified.
"""

from src.modules.platform.domain.entities.user import User
from src.modules.platform.ports.outbound.event_bus_port import IEventBus
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork
from src.modules.quality.application.dto.controlled_document_dto import LockCommand
from src.modules.quality.application.dto.sequence_dto import SequenceResult
from src.modules.quality.application.dto.sequence_dto import SequenceSummaryResult
from src.modules.quality.application.use_cases._controlled_documents.base import (
    LockControlledDocument,
)
from src.modules.quality.application.use_cases._controlled_documents.base import (
    UnlockControlledDocument,
)
from src.modules.quality.application.use_cases.sequence._kind import KIND
from src.modules.quality.domain.entities.sequence import Sequence
from src.modules.quality.ports.outbound.repositories.sequence_repository import ISequenceRepository


class LockSequence(LockControlledDocument[Sequence, SequenceResult, SequenceSummaryResult]):
    _kind = KIND

    def __init__(
        self, sequence_repo: ISequenceRepository, event_bus: IEventBus, *, uow: IUnitOfWork
    ) -> None:
        super().__init__(sequence_repo, event_bus, uow=uow)

    async def execute(self, actor: User, sequence_id: int, cmd: LockCommand) -> SequenceResult:
        return await self._lock(actor, sequence_id, cmd)


class UnlockSequence(UnlockControlledDocument[Sequence, SequenceResult, SequenceSummaryResult]):
    """Ends the caller's own edit lock, or with `force` someone else's, which
    needs manage:sequences; that editor is notified."""

    _kind = KIND

    def __init__(
        self, sequence_repo: ISequenceRepository, event_bus: IEventBus, *, uow: IUnitOfWork
    ) -> None:
        super().__init__(sequence_repo, event_bus, uow=uow)

    async def execute(
        self, actor: User, sequence_id: int, *, force: bool = False
    ) -> SequenceResult:
        return await self._unlock(actor, sequence_id, force=force)
