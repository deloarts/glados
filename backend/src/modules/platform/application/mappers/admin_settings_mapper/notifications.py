"""
Maps the webhook notification settings entity to its result DTO.
"""

from src.modules.platform.application.dto.admin_settings_dto.notifications import (
    AdminNotificationSettingsResult,
)
from src.modules.platform.domain.entities.admin_settings.notifications import (
    AdminNotificationSettings,
)


class NotificationSettingsMapper:
    @staticmethod
    def notifications_to_result(e: AdminNotificationSettings) -> AdminNotificationSettingsResult:
        return AdminNotificationSettingsResult(
            id=e.id,
            public_id=e.public_id,
            webhook_timeout_seconds=e.webhook_timeout_seconds,
        )
