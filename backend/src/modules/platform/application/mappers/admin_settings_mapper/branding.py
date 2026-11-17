"""
Maps the branding settings entity to its result DTO.
"""

from src.modules.platform.application.dto.admin_settings_dto.branding import (
    AdminBrandingSettingsResult,
)
from src.modules.platform.domain.entities.admin_settings.branding import AdminBrandingSettings


class BrandingSettingsMapper:
    @staticmethod
    def branding_to_result(e: AdminBrandingSettings) -> AdminBrandingSettingsResult:
        return AdminBrandingSettingsResult(
            id=e.id,
            public_id=e.public_id,
            app_name=e.app_name,
            app_description=e.app_description,
            footer_text=e.footer_text,
            has_logo=e.logo_key is not None,
            has_favicon=e.favicon_key is not None,
            has_login_background_video=e.login_background_video_key is not None,
        )
