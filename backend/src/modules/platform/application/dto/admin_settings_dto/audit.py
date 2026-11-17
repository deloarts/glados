"""
Commands and results for the admin settings audit log.
"""

from datetime import datetime

from src.modules.platform.application.dto.base import ResultBase


class AdminSettingsAuditEntryResult(ResultBase):
    changed_at: datetime
    changed_by_id: int | None
    changed_by_username: str | None
    settings_domain: str
    summary: str
