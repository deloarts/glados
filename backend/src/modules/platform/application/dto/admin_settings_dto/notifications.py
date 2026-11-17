"""
Commands and results for the outbound webhook notification settings.
"""

from pydantic import BaseModel
from pydantic import Field

from src.modules.platform.application.dto.base import ResultBase


class UpdateNotificationSettingsCommand(BaseModel):
    # Per-delivery HTTP timeout for outbound webhook subscriptions, see
    # dispatch_event_to_webhooks.py. Full-replace like every other field in
    # this command.
    webhook_timeout_seconds: int = Field(default=10, ge=1, le=120)


class AdminNotificationSettingsResult(ResultBase):
    webhook_timeout_seconds: int
