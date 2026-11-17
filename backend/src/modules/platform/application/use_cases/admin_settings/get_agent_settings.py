"""
Returns the AI agent settings for read:settings holders.
"""

from src.modules.platform.application.dto.admin_settings_dto.agents import AdminAgentSettingsResult
from src.modules.platform.application.mappers.admin_settings_mapper.agents import (
    AgentSettingsMapper,
)
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.services.settings_rules import SettingsRules
from src.modules.platform.ports.outbound.platform_settings_repository import (
    IPlatformSettingsRepository,
)


class GetAgentSettings:
    def __init__(self, repo: IPlatformSettingsRepository) -> None:
        self._repo = repo

    async def execute(self, actor: User) -> AdminAgentSettingsResult:
        SettingsRules.assert_can_read(actor)
        return AgentSettingsMapper.agents_to_result(await self._repo.get_agents())
