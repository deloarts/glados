"""
Retrieves a single API key by ID or lists API keys with pagination.
"""

from src.modules.platform.application.dto.api_key_dto import ApiKeyResult
from src.modules.platform.application.mappers.api_key_mapper import ApiKeyMapper
from src.modules.platform.application.services.lookup import found_or_raise
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.exceptions import ApiKeyNotFoundError
from src.modules.platform.domain.services.api_key_rules import ApiKeyRules
from src.modules.platform.ports.outbound.repositories.api_key_repository import ApiKeyFilterDto
from src.modules.platform.ports.outbound.repositories.api_key_repository import IApiKeyRepository


class PaginatedApiKeys:
    def __init__(self, total: int, items: list[ApiKeyResult]):
        self.total = total
        self.items = items


class GetApiKey:
    def __init__(self, key_repo: IApiKeyRepository) -> None:
        self._keys = key_repo

    async def execute(self, actor: User, key_id: int) -> ApiKeyResult:
        ApiKeyRules.assert_can_manage(actor)
        key = found_or_raise(
            await self._keys.get_by_id(key_id), ApiKeyNotFoundError, f"API key #{key_id} not found."
        )
        return ApiKeyMapper.to_result(key)


class GetApiKeys:
    def __init__(self, key_repo: IApiKeyRepository) -> None:
        self._keys = key_repo

    async def execute(self, actor: User, filters: ApiKeyFilterDto) -> PaginatedApiKeys:
        ApiKeyRules.assert_can_manage(actor)
        total, keys = await self._keys.get_multi(filters)
        return PaginatedApiKeys(total=total, items=[ApiKeyMapper.to_result(k) for k in keys])
