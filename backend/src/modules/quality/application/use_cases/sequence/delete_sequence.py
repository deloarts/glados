"""
Deletes the latest revision of a sequence for good, as long as it is a
draft; a released revision is kept as a record. Drafts go by their creator
or a manager. The revision before it, if any, becomes the latest and valid
one again.
"""

from src.modules.platform.domain.entities.user import User
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork
from src.modules.quality.application.dto.sequence_dto import SequenceResult
from src.modules.quality.application.dto.sequence_dto import SequenceSummaryResult
from src.modules.quality.application.use_cases._controlled_documents.base import (
    DeleteControlledDocument,
)
from src.modules.quality.application.use_cases.sequence._kind import KIND
from src.modules.quality.domain.entities.sequence import Sequence
from src.modules.quality.ports.outbound.repositories.sequence_repository import ISequenceRepository


class DeleteSequence(DeleteControlledDocument[Sequence, SequenceResult, SequenceSummaryResult]):
    _kind = KIND

    def __init__(self, sequence_repo: ISequenceRepository, *, uow: IUnitOfWork) -> None:
        super().__init__(sequence_repo, uow=uow)

    async def execute(self, actor: User, sequence_id: int) -> None:
        await self._delete(actor, sequence_id)
