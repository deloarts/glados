"""
Abstract interface for API key usage log persistence. Append-only,
entries are written by DatabaseLoggingMiddleware for every request
authenticated with an API key, and read back by the key-management API.
"""

from dataclasses import dataclass
from typing import Protocol
from typing import runtime_checkable

from src.modules.platform.domain.entities.api_key_usage_log import ApiKeyUsageLogEntry


@dataclass
class ApiKeyUsageLogFilterDto:
    skip: int | None = None
    limit: int | None = None


@runtime_checkable
class IApiKeyUsageLogRepository(Protocol):
    async def append(self, entry: ApiKeyUsageLogEntry) -> ApiKeyUsageLogEntry: ...

    async def get_by_key_id(
        self, key_id: int, filters: ApiKeyUsageLogFilterDto
    ) -> tuple[int, list[ApiKeyUsageLogEntry]]: ...
