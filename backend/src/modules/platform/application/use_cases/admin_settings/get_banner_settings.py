"""
Returns the current announcement-banner admin settings for read:settings
holders, routing the GET through the use-case layer like its sibling
settings-section GETs.
"""

from src.modules.platform.application.dto.admin_settings_dto.banner import AdminBannerSettingsResult
from src.modules.platform.application.mappers.admin_settings_mapper.banner import (
    BannerSettingsMapper,
)
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.services.settings_rules import SettingsRules
from src.modules.platform.ports.outbound.platform_settings_repository import (
    IPlatformSettingsRepository,
)


class GetBannerSettings:
    def __init__(self, repo: IPlatformSettingsRepository) -> None:
        self._repo = repo

    async def execute(self, actor: User) -> AdminBannerSettingsResult:
        SettingsRules.assert_can_read(actor)
        return BannerSettingsMapper.banner_to_result(await self._repo.get_banner())
