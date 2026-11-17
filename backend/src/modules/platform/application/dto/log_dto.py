"""
Input filters and output results for log use cases.
"""

from datetime import datetime

from src.modules.platform.application.dto.base import ResultBase


class LogEntryResult(ResultBase):
    timestamp: datetime
    user_id: int | None
    username: str | None
    level: str
    message: str | None
    method: str | None
    path: str | None
    status_code: int | None
    request_id: str | None
