"""
Retrieves personal access tokens (one or paginated for the acting user), enforcing
ownership/management permissions.
"""

from src.modules.platform.application.dto.pat_dto import PatResult
from src.modules.platform.application.mappers.pat_mapper import PatMapper
from src.modules.platform.application.services.lookup import found_or_raise
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.exceptions import PatNotFoundError
from src.modules.platform.domain.services.pat_rules import PatRules
from src.modules.platform.ports.outbound.repositories.pat_repository import IPatRepository
from src.modules.platform.ports.outbound.repositories.pat_repository import PatFilterDto


class PaginatedPats:
    def __init__(self, total: int, items: list[PatResult]):
        self.total = total
        self.items = items


class GetPat:
    def __init__(self, pat_repo: IPatRepository) -> None:
        self._pats = pat_repo

    async def execute(self, actor: User, pat_id: int) -> PatResult:
        token = found_or_raise(
            await self._pats.get_by_id(pat_id),
            PatNotFoundError,
            f"Personal access token #{pat_id} not found.",
        )
        PatRules.assert_can_manage(actor, token)
        return PatMapper.to_result(token)


class GetPats:
    def __init__(self, pat_repo: IPatRepository) -> None:
        self._pats = pat_repo

    async def execute(self, actor: User, filters: PatFilterDto) -> PaginatedPats:
        """Always scoped to the acting user's own tokens, there is no
        cross-user listing endpoint."""
        total, tokens = await self._pats.get_multi_for_user(actor.id, filters)
        return PaginatedPats(total=total, items=[PatMapper.to_result(t) for t in tokens])
