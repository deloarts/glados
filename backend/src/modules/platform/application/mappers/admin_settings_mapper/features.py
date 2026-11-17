"""
Maps the feature flag settings entity to its result DTO.
"""

from src.modules.platform.application.dto.admin_settings_dto.features import (
    AdminFeatureSettingsResult,
)
from src.modules.platform.domain.entities.admin_settings.features import AdminFeatureSettings


class FeatureSettingsMapper:
    @staticmethod
    def features_to_result(e: AdminFeatureSettings) -> AdminFeatureSettingsResult:
        return AdminFeatureSettingsResult(
            id=e.id,
            public_id=e.public_id,
            enable_email_notifications=e.enable_email_notifications,
            enable_production_planning=e.enable_production_planning,
            allow_private_webhooks=e.allow_private_webhooks,
            enable_calculations=e.enable_calculations,
            enable_checklists=e.enable_checklists,
            enable_devices=e.enable_devices,
            enable_sequences=e.enable_sequences,
            enable_todos=e.enable_todos,
        )
