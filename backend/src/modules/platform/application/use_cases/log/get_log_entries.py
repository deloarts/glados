"""
Retrieves audit log entries matching the given filters, gated by the read:settings permission.
"""

from src.modules.platform.application.dto.log_dto import LogEntryResult
from src.modules.platform.application.mappers.log_mapper import LogMapper
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.services.log_rules import LogRules
from src.modules.platform.ports.outbound.repositories.log_repository import ILogRepository
from src.modules.platform.ports.outbound.repositories.log_repository import LogFilterDto


class GetLogEntries:
    def __init__(self, log_repo: ILogRepository) -> None:
        self._log_repo = log_repo

    async def execute(self, actor: User, filters: LogFilterDto) -> tuple[int, list[LogEntryResult]]:
        LogRules.assert_can_read(actor)
        total, entries = await self._log_repo.get_multi(filters)
        return total, [LogMapper.to_result(e) for e in entries]
