"""
Pure domain entity. No SQLAlchemy, no Pydantic, no FastAPI.

level is always set:
  "HTTP"    - captured by DatabaseLoggingMiddleware (method/path/status_code filled)
  "INFO" / "WARNING" / "ERROR" / "DEBUG" / "CRITICAL", captured by DatabaseLogHandler
"""

from dataclasses import dataclass
from datetime import datetime

from src.shared_kernel.domain.entities.base import Entity


@dataclass
class LogEntry(Entity):
    timestamp: datetime
    user_id: int | None
    username: str | None
    level: str
    message: str | None
    # only set for HTTP logs
    method: str | None
    path: str | None
    status_code: int | None
    # set for all log entries emitted inside an HTTP request
    request_id: str | None
