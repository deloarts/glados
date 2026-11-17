"""
HTTP request and response schemas for the outbound webhook notification
settings.
"""

from pydantic import BaseModel
from pydantic import Field

from src.modules.platform.adapters.inbound.api.schemas.base import EntityResponse


class UpdateNotificationSettingsRequest(BaseModel):
    # Mirrored on UpdateNotificationSettingsCommand per this module's
    # docstring.
    webhook_timeout_seconds: int = Field(default=10, ge=1, le=120)


class AdminNotificationSettingsResponse(EntityResponse):
    webhook_timeout_seconds: int
