"""
Commands and results for the feature flag settings.
"""

from pydantic import BaseModel

from src.modules.platform.application.dto.base import ResultBase


class UpdateFeatureSettingsCommand(BaseModel):
    """Partial update, None means "leave as-is".

    The admin tab only offers the flags something actually enforces. With
    replace semantics the unsurfaced flags would be reset to these defaults on
    every save, silently rewriting settings the admin never saw.
    """

    enable_email_notifications: bool | None = None
    enable_production_planning: bool | None = None
    allow_private_webhooks: bool | None = None
    enable_calculations: bool | None = None
    enable_checklists: bool | None = None
    enable_devices: bool | None = None
    enable_sequences: bool | None = None
    enable_todos: bool | None = None


class AdminFeatureSettingsResult(ResultBase):
    enable_email_notifications: bool
    enable_production_planning: bool
    allow_private_webhooks: bool
    enable_calculations: bool
    enable_checklists: bool
    enable_devices: bool
    enable_sequences: bool
    enable_todos: bool
