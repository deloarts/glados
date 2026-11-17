"""
Abstract interface for PAT usage log persistence. Append-only, entries
are written by DatabaseLoggingMiddleware for every request authenticated
with a PAT, and read back by the token-management API.
"""

from dataclasses import dataclass
from typing import Protocol
from typing import runtime_checkable

from src.modules.platform.domain.entities.pat_usage_log import PatUsageLogEntry


@dataclass
class PatUsageLogFilterDto:
    skip: int | None = None
    limit: int | None = None


@runtime_checkable
class IPatUsageLogRepository(Protocol):
    async def append(self, entry: PatUsageLogEntry) -> PatUsageLogEntry: ...

    async def get_by_pat_id(
        self, pat_id: int, filters: PatUsageLogFilterDto
    ) -> tuple[int, list[PatUsageLogEntry]]: ...
