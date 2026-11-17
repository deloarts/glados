"""
Routes the /host GET through the use-case layer, matching the module's
other GETs (GetAllAdminSettings, GetHostStats, GetAdminSettingsAudit)
instead of an inline permission check and direct mapper call in the
adapter.
"""

from src.modules.platform.application.dto.admin_settings_dto.host import AdminHostSettingsResult
from src.modules.platform.application.mappers.admin_settings_mapper.host import HostSettingsMapper
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.services.settings_rules import SettingsRules
from src.modules.platform.ports.outbound.platform_settings_repository import (
    IPlatformSettingsRepository,
)


class GetHostSettings:
    def __init__(self, repo: IPlatformSettingsRepository, domain: str) -> None:
        self._repo = repo
        self._domain = domain

    async def execute(self, actor: User) -> AdminHostSettingsResult:
        SettingsRules.assert_can_read(actor)
        return HostSettingsMapper.host_to_result(await self._repo.get_host(), self._domain)
