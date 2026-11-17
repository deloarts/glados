"""
Lists checklists, reads one, and lists the revisions of one. Another user's
personal checklist is filtered out of lists and answers like a missing row,
see ChecklistRules.can_view.
"""

from dataclasses import dataclass
from uuid import UUID

from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.value_objects.permission import Permission
from src.modules.quality.application.dto.checklist_dto import ChecklistResult
from src.modules.quality.application.dto.checklist_dto import ChecklistSummaryResult
from src.modules.quality.application.mappers.checklist_mapper import ChecklistMapper
from src.modules.quality.application.use_cases._controlled_documents.base import (
    GetControlledDocument,
)
from src.modules.quality.application.use_cases._controlled_documents.base import (
    GetControlledDocumentByPublicId,
)
from src.modules.quality.application.use_cases._controlled_documents.base import (
    GetControlledDocumentRevisions,
)
from src.modules.quality.application.use_cases.checklist._kind import KIND
from src.modules.quality.domain.entities.checklist import Checklist
from src.modules.quality.ports.outbound.repositories.checklist_repository import ChecklistFilterDto
from src.modules.quality.ports.outbound.repositories.checklist_repository import (
    IChecklistRepository,
)


@dataclass
class ChecklistListQuery:
    skip: int | None = None
    limit: int | None = None
    project_id: int | None = None
    product_id: int | None = None
    related_product_id: int | None = None
    # Only checklists the actor created, whatever they belong to.
    mine: bool = False
    owner: str | None = None
    type: str | None = None
    verdict: str | None = None
    released: bool | None = None
    search: str | None = None
    latest_only: bool = True
    order_by: str | None = None
    order_dir: str | None = None


@dataclass
class PaginatedChecklists:
    total: int
    items: list[ChecklistSummaryResult]


class GetChecklists:
    def __init__(self, checklist_repo: IChecklistRepository) -> None:
        self._checklists = checklist_repo

    async def execute(self, actor: User, query: ChecklistListQuery) -> PaginatedChecklists:
        sees_all = actor.has_permission(Permission.MANAGE_CHECKLISTS)
        filters = ChecklistFilterDto(
            skip=query.skip,
            limit=query.limit,
            project_id=query.project_id,
            product_id=query.product_id,
            related_product_id=query.related_product_id,
            creator_id=actor.id if query.mine else None,
            owner=query.owner,
            type=query.type,
            verdict=query.verdict,
            released=query.released,
            search=query.search,
            latest_only=query.latest_only,
            visible_to_user_id=None if sees_all else actor.id,
            order_by=query.order_by,
            order_dir=query.order_dir,
        )
        total, items = await self._checklists.get_multi(filters)
        return PaginatedChecklists(
            total=total, items=[ChecklistMapper.to_summary_result(i) for i in items]
        )


class GetChecklist(GetControlledDocument[Checklist, ChecklistResult, ChecklistSummaryResult]):
    _kind = KIND

    def __init__(self, checklist_repo: IChecklistRepository) -> None:
        super().__init__(checklist_repo)

    async def execute(self, actor: User, checklist_id: int) -> ChecklistResult:
        return await self._get(actor, checklist_id)


class GetChecklistByPublicId(
    GetControlledDocumentByPublicId[Checklist, ChecklistResult, ChecklistSummaryResult]
):
    """For links to a checklist, which carry its public id."""

    _kind = KIND

    def __init__(self, checklist_repo: IChecklistRepository) -> None:
        super().__init__(checklist_repo)

    async def execute(self, actor: User, public_id: UUID) -> ChecklistResult:
        return await self._get(actor, public_id)


class GetChecklistRevisions(
    GetControlledDocumentRevisions[Checklist, ChecklistResult, ChecklistSummaryResult]
):
    """Every revision of the checklist's lineage, newest first. Revisions
    share their owner, so seeing one means seeing all."""

    _kind = KIND

    def __init__(self, checklist_repo: IChecklistRepository) -> None:
        super().__init__(checklist_repo)

    async def execute(self, actor: User, checklist_id: int) -> list[ChecklistSummaryResult]:
        return await self._get(actor, checklist_id)
