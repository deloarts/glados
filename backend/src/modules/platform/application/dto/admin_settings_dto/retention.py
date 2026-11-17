"""
Commands and results for the data retention settings.
"""

from pydantic import BaseModel

from src.modules.platform.application.dto.base import ResultBase


class UpdateRetentionSettingsCommand(BaseModel):
    log_retention_days: int = 90
    audit_retention_days: int = 365
    soft_delete_cleanup_days: int = 0
    # None keeps the stored period.
    meeting_retention_days: int | None = None


class AdminRetentionSettingsResult(ResultBase):
    log_retention_days: int
    audit_retention_days: int
    soft_delete_cleanup_days: int
    meeting_retention_days: int
