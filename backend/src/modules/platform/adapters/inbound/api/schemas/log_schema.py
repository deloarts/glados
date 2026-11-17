"""
Pydantic models for the HTTP layer only.
"""

from datetime import datetime

from src.modules.platform.adapters.inbound.api.schemas.base import EntityResponse
from src.modules.platform.adapters.inbound.api.schemas.base import ResponseModel


class LogEntryResponse(EntityResponse):
    timestamp: datetime
    user_id: int | None
    username: str | None
    level: str
    message: str | None
    method: str | None
    path: str | None
    status_code: int | None
    request_id: str | None


class LogEntriesResponse(ResponseModel):
    total: int
    items: list[LogEntryResponse]
