"""
HTTP request and response schemas for the admin settings audit log.
"""

from datetime import datetime

from src.modules.platform.adapters.inbound.api.schemas.base import EntityResponse


class AdminSettingsAuditEntryResponse(EntityResponse):
    changed_at: datetime
    changed_by_id: int | None
    changed_by_username: str | None
    settings_domain: str
    summary: str
