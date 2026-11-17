"""
Maps the host settings entity to its result DTO.
"""

from src.modules.platform.application.dto.admin_settings_dto.host import AdminHostSettingsResult
from src.modules.platform.domain.entities.admin_settings.host import AdminHostSettings


class HostSettingsMapper:
    @staticmethod
    def host_to_result(e: AdminHostSettings, domain: str) -> AdminHostSettingsResult:
        return AdminHostSettingsResult(
            id=e.id,
            public_id=e.public_id,
            domain=domain,
        )
