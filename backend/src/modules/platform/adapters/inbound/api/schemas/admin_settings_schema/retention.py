"""
HTTP request and response schemas for the data retention settings.
"""

from pydantic import BaseModel

from src.modules.platform.adapters.inbound.api.schemas.base import EntityResponse


class UpdateRetentionSettingsRequest(BaseModel):
    log_retention_days: int = 90
    audit_retention_days: int = 365
    soft_delete_cleanup_days: int = 0
    # Left out, the period stays as it is.
    meeting_retention_days: int | None = None


class AdminRetentionSettingsResponse(EntityResponse):
    log_retention_days: int
    audit_retention_days: int
    soft_delete_cleanup_days: int
    meeting_retention_days: int
