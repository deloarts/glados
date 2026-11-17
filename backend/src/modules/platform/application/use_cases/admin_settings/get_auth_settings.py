"""
Routes the /auth GET through the use-case layer, matching the module's
other GETs (GetAllAdminSettings, GetHostStats, GetAdminSettingsAudit)
instead of an inline permission check and direct mapper call in the adapter.
"""

from src.modules.platform.application.dto.admin_settings_dto.auth import AdminAuthSettingsResult
from src.modules.platform.application.mappers.admin_settings_mapper.auth import AuthSettingsMapper
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.services.settings_rules import SettingsRules
from src.modules.platform.ports.outbound.platform_settings_repository import (
    IPlatformSettingsRepository,
)


class GetAuthSettings:
    def __init__(self, repo: IPlatformSettingsRepository) -> None:
        self._repo = repo

    async def execute(self, actor: User) -> AdminAuthSettingsResult:
        SettingsRules.assert_can_read(actor)
        return AuthSettingsMapper.auth_to_result(await self._repo.get_auth())
