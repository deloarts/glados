"""
Lists flow sequences and reads one. Every logged-in user sees every
sequence, like the product it belongs to.
"""

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from src.modules.platform.domain.entities.user import User
from src.modules.quality.application.dto.sequence_dto import SequenceResult
from src.modules.quality.application.dto.sequence_dto import SequenceSummaryResult
from src.modules.quality.application.mappers.sequence_mapper import SequenceMapper
from src.modules.quality.application.use_cases._controlled_documents.base import (
    GetControlledDocument,
)
from src.modules.quality.application.use_cases._controlled_documents.base import (
    GetControlledDocumentByPublicId,
)
from src.modules.quality.application.use_cases._controlled_documents.base import (
    GetControlledDocumentRevisions,
)
from src.modules.quality.application.use_cases.sequence._context import SequenceContextLoader
from src.modules.quality.application.use_cases.sequence._kind import KIND
from src.modules.quality.domain.entities.sequence import Sequence
from src.modules.quality.domain.services.sequence_rules import freeze_names
from src.modules.quality.domain.services.sequence_rules import references_of
from src.modules.quality.ports.outbound.repositories.sequence_repository import ISequenceRepository
from src.modules.quality.ports.outbound.repositories.sequence_repository import SequenceFilterDto
from src.modules.workspace.ports.outbound.workspace_queries import IProductDeviceKindQueries
from src.modules.workspace.ports.outbound.workspace_queries import IProductDeviceQueries
from src.modules.workspace.ports.outbound.workspace_queries import IProductVariantQueries


@dataclass
class SequenceListQuery:
    skip: int | None = None
    limit: int | None = None
    product_id: int | None = None
    # Only sequences the actor created.
    mine: bool = False
    search: str | None = None
    released: bool | None = None
    latest_only: bool = True
    order_by: str | None = None
    order_dir: str | None = None


@dataclass
class PaginatedSequences:
    total: int
    items: list[SequenceSummaryResult]


class GetSequences:
    def __init__(self, sequence_repo: ISequenceRepository) -> None:
        self._sequences = sequence_repo

    async def execute(self, actor: User, query: SequenceListQuery) -> PaginatedSequences:
        filters = SequenceFilterDto(
            skip=query.skip,
            limit=query.limit,
            product_id=query.product_id,
            creator_id=actor.id if query.mine else None,
            search=query.search,
            released=query.released,
            latest_only=query.latest_only,
            order_by=query.order_by,
            order_dir=query.order_dir,
        )
        total, items = await self._sequences.get_multi(filters)
        return PaginatedSequences(
            total=total, items=[SequenceMapper.to_summary_result(i) for i in items]
        )


class GetSequence(GetControlledDocument[Sequence, SequenceResult, SequenceSummaryResult]):
    _kind = KIND

    def __init__(self, sequence_repo: ISequenceRepository) -> None:
        super().__init__(sequence_repo)

    async def execute(self, actor: User, sequence_id: int) -> SequenceResult:
        return await self._get(actor, sequence_id)


class GetSequenceByPublicId(
    GetControlledDocumentByPublicId[Sequence, SequenceResult, SequenceSummaryResult]
):
    """For links to a sequence, which carry its public id."""

    _kind = KIND

    def __init__(self, sequence_repo: ISequenceRepository) -> None:
        super().__init__(sequence_repo)

    async def execute(self, actor: User, public_id: UUID) -> SequenceResult:
        return await self._get(actor, public_id)


class GetSequenceRevisions(
    GetControlledDocumentRevisions[Sequence, SequenceResult, SequenceSummaryResult]
):
    """Every revision of the sequence's lineage, newest first."""

    _kind = KIND

    def __init__(self, sequence_repo: ISequenceRepository) -> None:
        super().__init__(sequence_repo)

    async def execute(self, actor: User, sequence_id: int) -> list[SequenceSummaryResult]:
        return await self._get(actor, sequence_id)


class GetSequenceNames(GetControlledDocument[Sequence, SequenceResult, SequenceSummaryResult]):
    """The names a sequence's steps show, in the shape a release freezes
    them (see freeze_names): the frozen names of a released revision, and
    the product's current names for a draft, archived devices the draft
    still refers to included. The web app resolves a draft's names from
    the product's devices itself; an agent reads them here, so a step
    reads with device and position names instead of ids."""

    _kind = KIND

    def __init__(
        self,
        sequence_repo: ISequenceRepository,
        device_repo: IProductDeviceQueries,
        kind_repo: IProductDeviceKindQueries,
        variant_repo: IProductVariantQueries,
    ) -> None:
        super().__init__(sequence_repo)
        self._context = SequenceContextLoader(device_repo, kind_repo, variant_repo)

    async def execute(self, actor: User, sequence_id: int) -> dict[str, Any]:
        sequence = await self._load(sequence_id)
        KIND.rules.assert_can_view(actor, sequence)
        if sequence.is_released and sequence.frozen is not None:
            return sequence.frozen
        context = await self._context.load(sequence.product_id, references_of(sequence.steps))
        return freeze_names(sequence.product_number, context)
