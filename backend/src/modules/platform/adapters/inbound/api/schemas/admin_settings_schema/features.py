"""
HTTP request and response schemas for the feature flag settings.
"""

from pydantic import BaseModel

from src.modules.platform.adapters.inbound.api.schemas.base import EntityResponse


class UpdateFeatureSettingsRequest(BaseModel):
    enable_email_notifications: bool | None = None
    enable_production_planning: bool | None = None
    allow_private_webhooks: bool | None = None
    enable_calculations: bool | None = None
    enable_checklists: bool | None = None
    enable_devices: bool | None = None
    enable_sequences: bool | None = None
    enable_todos: bool | None = None


class AdminFeatureSettingsResponse(EntityResponse):
    enable_email_notifications: bool
    enable_production_planning: bool
    allow_private_webhooks: bool
    enable_calculations: bool
    enable_checklists: bool
    enable_devices: bool
    enable_sequences: bool
    enable_todos: bool
