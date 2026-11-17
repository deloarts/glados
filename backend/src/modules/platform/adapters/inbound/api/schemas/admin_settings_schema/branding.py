"""
HTTP request and response schemas for the UI branding settings.
"""

from pydantic import BaseModel

from src.modules.platform.adapters.inbound.api.schemas.base import EntityResponse


class UpdateBrandingSettingsRequest(BaseModel):
    app_name: str
    app_description: str | None = None
    footer_text: str | None = None


class AdminBrandingSettingsResponse(EntityResponse):
    app_name: str
    app_description: str | None
    footer_text: str | None
    has_logo: bool
    has_favicon: bool
    has_login_background_video: bool
