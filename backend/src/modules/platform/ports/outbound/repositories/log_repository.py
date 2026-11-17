"""
Abstract interface for log persistence.
The application layer depends on this, never on the SQLAlchemy implementation.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from typing import runtime_checkable

from src.modules.platform.domain.entities.log_entry import LogEntry


@dataclass
class LogFilterDto:
    skip: int | None = None
    limit: int | None = None
    user_id: int | None = None
    username_contains: str | None = None
    status_code: int | None = None
    level: str | None = None
    method: str | None = None
    path_contains: str | None = None
    message_contains: str | None = None
    request_id: str | None = None
    from_timestamp: datetime | None = None
    to_timestamp: datetime | None = None


@runtime_checkable
class ILogRepository(Protocol):
    async def get_multi(self, filters: LogFilterDto) -> tuple[int, list[LogEntry]]: ...

    async def save(self, entry: LogEntry) -> LogEntry: ...
