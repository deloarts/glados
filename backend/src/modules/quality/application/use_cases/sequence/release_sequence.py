"""
Releases a sequence (the sign-off that makes it read-only for good) and
marks a released revision invalid. The author may release their own
sequence. A release needs every device, position and variant the steps
name to be live, and freezes the names the sequence shows (devices with
their positions and initial positions, variants) into the revision, so
renaming a device later never changes a released sequence. Releasing a
later revision supersedes the one before it. A revision found to be wrong
is marked invalid with a reason, which needs manage:sequences, and is
corrected by a new revision.
"""

from src.modules.platform.domain.entities.user import User
from src.modules.platform.ports.outbound.event_bus_port import IEventBus
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork
from src.modules.quality.application.dto.controlled_document_dto import MarkInvalidCommand
from src.modules.quality.application.dto.sequence_dto import SequenceResult
from src.modules.quality.application.dto.sequence_dto import SequenceSummaryResult
from src.modules.quality.application.use_cases._controlled_documents.base import (
    MarkControlledDocumentInvalid,
)
from src.modules.quality.application.use_cases._controlled_documents.base import (
    ReleaseControlledDocument,
)
from src.modules.quality.application.use_cases.sequence._context import SequenceContextLoader
from src.modules.quality.application.use_cases.sequence._kind import KIND
from src.modules.quality.domain.entities.sequence import Sequence
from src.modules.quality.domain.services.sequence_rules import check_content
from src.modules.quality.domain.services.sequence_rules import freeze_names
from src.modules.quality.ports.outbound.repositories.sequence_repository import ISequenceRepository
from src.modules.workspace.ports.outbound.workspace_queries import IProductDeviceKindQueries
from src.modules.workspace.ports.outbound.workspace_queries import IProductDeviceQueries
from src.modules.workspace.ports.outbound.workspace_queries import IProductVariantQueries


class ReleaseSequence(ReleaseControlledDocument[Sequence, SequenceResult, SequenceSummaryResult]):
    """Before the shared release runs, the content is checked with no
    archived reference kept and the names are frozen onto the revision, in
    the same unit of work."""

    _kind = KIND

    def __init__(
        self,
        sequence_repo: ISequenceRepository,
        device_repo: IProductDeviceQueries,
        kind_repo: IProductDeviceKindQueries,
        variant_repo: IProductVariantQueries,
        *,
        uow: IUnitOfWork,
    ) -> None:
        super().__init__(sequence_repo, uow=uow)
        self._sequences = sequence_repo
        self._context = SequenceContextLoader(device_repo, kind_repo, variant_repo)

    async def execute(self, actor: User, sequence_id: int) -> SequenceResult:
        KIND.rules.assert_can_release_any(actor)
        sequence = await self._load(sequence_id)
        KIND.rules.assert_can_release(actor, sequence)
        context = await self._context.load(sequence.product_id)
        check_content(sequence.steps, context)
        sequence.frozen = freeze_names(sequence.product_number, context)
        await self._sequences.save(sequence)
        return await self._release(actor, sequence_id)


class MarkSequenceInvalid(
    MarkControlledDocumentInvalid[Sequence, SequenceResult, SequenceSummaryResult]
):
    _kind = KIND

    def __init__(
        self, sequence_repo: ISequenceRepository, event_bus: IEventBus, *, uow: IUnitOfWork
    ) -> None:
        super().__init__(sequence_repo, event_bus, uow=uow)

    async def execute(
        self, actor: User, sequence_id: int, cmd: MarkInvalidCommand
    ) -> SequenceResult:
        return await self._mark_invalid(actor, sequence_id, cmd)
