"""
Routes the /notification GET through the use-case layer, matching the
module's other GETs (GetAllAdminSettings, GetHostStats,
GetAdminSettingsAudit) instead of an inline permission check and direct
mapper call in the adapter.
"""

from src.modules.platform.application.dto.admin_settings_dto.notifications import (
    AdminNotificationSettingsResult,
)
from src.modules.platform.application.mappers.admin_settings_mapper.notifications import (
    NotificationSettingsMapper,
)
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.services.settings_rules import SettingsRules
from src.modules.platform.ports.outbound.platform_settings_repository import (
    IPlatformSettingsRepository,
)


class GetNotificationSettings:
    def __init__(self, repo: IPlatformSettingsRepository) -> None:
        self._repo = repo

    async def execute(self, actor: User) -> AdminNotificationSettingsResult:
        SettingsRules.assert_can_read(actor)
        return NotificationSettingsMapper.notifications_to_result(
            await self._repo.get_notifications()
        )
