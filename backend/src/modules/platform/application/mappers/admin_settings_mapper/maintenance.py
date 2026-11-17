"""
Maps the maintenance mode settings entity to its result DTO.
"""

from src.modules.platform.application.dto.admin_settings_dto.maintenance import (
    AdminMaintenanceSettingsResult,
)
from src.modules.platform.domain.entities.admin_settings.maintenance import AdminMaintenanceSettings


class MaintenanceSettingsMapper:
    @staticmethod
    def maintenance_to_result(e: AdminMaintenanceSettings) -> AdminMaintenanceSettingsResult:
        return AdminMaintenanceSettingsResult(
            id=e.id,
            public_id=e.public_id,
            enabled=e.enabled,
            message=e.message,
            allowed_ips=list(e.allowed_ips),
        )
