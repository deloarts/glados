"""
Maps the banner settings entity to its result DTO.
"""

from src.modules.platform.application.dto.admin_settings_dto.banner import AdminBannerSettingsResult
from src.modules.platform.domain.entities.admin_settings.banner import AdminBannerSettings


class BannerSettingsMapper:
    @staticmethod
    def banner_to_result(e: AdminBannerSettings) -> AdminBannerSettingsResult:
        return AdminBannerSettingsResult(
            id=e.id,
            public_id=e.public_id,
            enabled=e.enabled,
            text=e.text,
            severity=e.severity,
            shows_from=e.shows_from,
            shows_until=e.shows_until,
            dismissable=e.dismissable,
            updated_at=e.updated_at,
        )
