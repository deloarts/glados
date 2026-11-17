"""
Commands and results for the UI branding settings.
"""

from pydantic import BaseModel

from src.modules.platform.application.dto.base import ResultBase


class UpdateBrandingSettingsCommand(BaseModel):
    app_name: str
    app_description: str | None = None
    footer_text: str | None = None


class AdminBrandingSettingsResult(ResultBase):
    app_name: str
    app_description: str | None
    footer_text: str | None
    has_logo: bool
    has_favicon: bool
    has_login_background_video: bool
