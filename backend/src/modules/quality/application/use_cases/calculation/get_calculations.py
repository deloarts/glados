"""
Lists saved calculations and reads one. Another user's personal
calculation is filtered out of lists and answers like a missing row, see
CalculationRules.can_view.
"""

from dataclasses import dataclass
from uuid import UUID

from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.value_objects.permission import Permission
from src.modules.quality.application.dto.calculation_dto import CalculationResult
from src.modules.quality.application.dto.calculation_dto import CalculationSummaryResult
from src.modules.quality.application.mappers.calculation_mapper import CalculationMapper
from src.modules.quality.application.use_cases._controlled_documents.base import (
    GetControlledDocument,
)
from src.modules.quality.application.use_cases._controlled_documents.base import (
    GetControlledDocumentByPublicId,
)
from src.modules.quality.application.use_cases._controlled_documents.base import (
    GetControlledDocumentRevisions,
)
from src.modules.quality.application.use_cases.calculation._kind import KIND
from src.modules.quality.domain.entities.calculation import Calculation
from src.modules.quality.ports.outbound.repositories.calculation_repository import (
    CalculationFilterDto,
)
from src.modules.quality.ports.outbound.repositories.calculation_repository import (
    ICalculationRepository,
)


@dataclass
class CalculationListQuery:
    skip: int | None = None
    limit: int | None = None
    project_id: int | None = None
    product_id: int | None = None
    related_product_id: int | None = None
    product_device_id: int | None = None
    personal_only: bool = False
    # Only calculations the actor created, whatever they belong to.
    mine: bool = False
    tool: str | None = None
    search: str | None = None
    owner: str | None = None
    released: bool | None = None
    latest_only: bool = True
    order_by: str | None = None
    order_dir: str | None = None


@dataclass
class PaginatedCalculations:
    total: int
    items: list[CalculationSummaryResult]


class GetCalculations:
    def __init__(self, calculation_repo: ICalculationRepository) -> None:
        self._calculations = calculation_repo

    async def execute(self, actor: User, query: CalculationListQuery) -> PaginatedCalculations:
        sees_all = actor.has_permission(Permission.MANAGE_CALCULATIONS)
        filters = CalculationFilterDto(
            skip=query.skip,
            limit=query.limit,
            project_id=query.project_id,
            product_id=query.product_id,
            related_product_id=query.related_product_id,
            product_device_id=query.product_device_id,
            creator_id=actor.id if query.mine else None,
            personal_only=query.personal_only,
            tool=query.tool,
            search=query.search,
            owner=query.owner,
            released=query.released,
            latest_only=query.latest_only,
            visible_to_user_id=None if sees_all else actor.id,
            order_by=query.order_by,
            order_dir=query.order_dir,
        )
        total, items = await self._calculations.get_multi(filters)
        return PaginatedCalculations(
            total=total, items=[CalculationMapper.to_summary_result(i) for i in items]
        )


class GetCalculation(
    GetControlledDocument[Calculation, CalculationResult, CalculationSummaryResult]
):
    _kind = KIND

    def __init__(self, calculation_repo: ICalculationRepository) -> None:
        super().__init__(calculation_repo)

    async def execute(self, actor: User, calculation_id: int) -> CalculationResult:
        return await self._get(actor, calculation_id)


class GetCalculationByPublicId(
    GetControlledDocumentByPublicId[Calculation, CalculationResult, CalculationSummaryResult]
):
    """For links to a saved calculation, which carry its public id."""

    _kind = KIND

    def __init__(self, calculation_repo: ICalculationRepository) -> None:
        super().__init__(calculation_repo)

    async def execute(self, actor: User, public_id: UUID) -> CalculationResult:
        return await self._get(actor, public_id)


class GetCalculationRevisions(
    GetControlledDocumentRevisions[Calculation, CalculationResult, CalculationSummaryResult]
):
    """Every revision of the calculation's lineage, newest first. Revisions
    share their owner, so seeing one means seeing all."""

    _kind = KIND

    def __init__(self, calculation_repo: ICalculationRepository) -> None:
        super().__init__(calculation_repo)

    async def execute(self, actor: User, calculation_id: int) -> list[CalculationSummaryResult]:
        return await self._get(actor, calculation_id)
