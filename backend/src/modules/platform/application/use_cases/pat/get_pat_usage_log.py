"""
Retrieves paginated usage log entries for a personal access token, enforcing management
permissions.
"""

from src.modules.platform.application.dto.pat_dto import PatUsageLogEntryResult
from src.modules.platform.application.mappers.pat_mapper import PatMapper
from src.modules.platform.application.services.lookup import found_or_raise
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.exceptions import PatNotFoundError
from src.modules.platform.domain.services.pat_rules import PatRules
from src.modules.platform.ports.outbound.repositories.pat_repository import IPatRepository
from src.modules.platform.ports.outbound.repositories.pat_usage_log_repository import (
    IPatUsageLogRepository,
)
from src.modules.platform.ports.outbound.repositories.pat_usage_log_repository import (
    PatUsageLogFilterDto,
)


class PaginatedPatUsageLog:
    def __init__(self, total: int, items: list[PatUsageLogEntryResult]):
        self.total = total
        self.items = items


class GetPatUsageLog:
    def __init__(
        self,
        pat_repo: IPatRepository,
        usage_log_repo: IPatUsageLogRepository,
    ) -> None:
        self._pats = pat_repo
        self._usage_log = usage_log_repo

    async def execute(
        self, actor: User, pat_id: int, filters: PatUsageLogFilterDto
    ) -> PaginatedPatUsageLog:
        token = found_or_raise(
            await self._pats.get_by_id(pat_id),
            PatNotFoundError,
            f"Personal access token #{pat_id} not found.",
        )
        PatRules.assert_can_manage(actor, token)

        total, entries = await self._usage_log.get_by_pat_id(pat_id, filters)
        return PaginatedPatUsageLog(
            total=total, items=[PatMapper.usage_to_result(e) for e in entries]
        )
