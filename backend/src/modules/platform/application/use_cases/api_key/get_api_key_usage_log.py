"""
Retrieves the usage log entries for a specific API key with pagination.
"""

from src.modules.platform.application.dto.api_key_dto import ApiKeyUsageLogEntryResult
from src.modules.platform.application.mappers.api_key_mapper import ApiKeyMapper
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.exceptions import ApiKeyNotFoundError
from src.modules.platform.domain.services.api_key_rules import ApiKeyRules
from src.modules.platform.ports.outbound.repositories.api_key_repository import IApiKeyRepository
from src.modules.platform.ports.outbound.repositories.api_key_usage_log_repository import (
    ApiKeyUsageLogFilterDto,
)
from src.modules.platform.ports.outbound.repositories.api_key_usage_log_repository import (
    IApiKeyUsageLogRepository,
)


class PaginatedApiKeyUsageLog:
    def __init__(self, total: int, items: list[ApiKeyUsageLogEntryResult]):
        self.total = total
        self.items = items


class GetApiKeyUsageLog:
    def __init__(
        self,
        key_repo: IApiKeyRepository,
        usage_log_repo: IApiKeyUsageLogRepository,
    ) -> None:
        self._keys = key_repo
        self._usage_log = usage_log_repo

    async def execute(
        self, actor: User, key_id: int, filters: ApiKeyUsageLogFilterDto
    ) -> PaginatedApiKeyUsageLog:
        ApiKeyRules.assert_can_manage(actor)

        if not await self._keys.get_by_id(key_id):
            raise ApiKeyNotFoundError(f"API key #{key_id} not found.")

        total, entries = await self._usage_log.get_by_key_id(key_id, filters)
        return PaginatedApiKeyUsageLog(
            total=total, items=[ApiKeyMapper.usage_to_result(e) for e in entries]
        )
