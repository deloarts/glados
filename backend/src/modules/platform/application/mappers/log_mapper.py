"""
Converts between LogEntry domain entity and DTOs.
"""

from src.modules.platform.application.dto.log_dto import LogEntryResult
from src.modules.platform.domain.entities.log_entry import LogEntry


class LogMapper:
    @staticmethod
    def to_result(entity: LogEntry) -> LogEntryResult:
        return LogEntryResult(
            id=entity.id,
            public_id=entity.public_id,
            timestamp=entity.timestamp,
            user_id=entity.user_id,
            username=entity.username,
            level=entity.level,
            message=entity.message,
            method=entity.method,
            path=entity.path,
            status_code=entity.status_code,
            request_id=entity.request_id,
        )
