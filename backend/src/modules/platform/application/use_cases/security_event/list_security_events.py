"""
Pages through the security log for the admin settings tab, newest first,
gated by the read:settings permission like the settings audit trail.
"""

from src.modules.platform.application.dto.security_event_dto import SecurityEventResult
from src.modules.platform.application.mappers.security_event_mapper import SecurityEventMapper
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.services.settings_rules import SettingsRules
from src.modules.platform.ports.outbound.repositories.security_event_repository import (
    ISecurityEventRepository,
)
from src.modules.platform.ports.outbound.repositories.security_event_repository import (
    SecurityEventFilterDto,
)


class ListSecurityEvents:
    def __init__(self, repo: ISecurityEventRepository) -> None:
        self._repo = repo

    async def execute(
        self, actor: User, filters: SecurityEventFilterDto
    ) -> tuple[int, list[SecurityEventResult]]:
        SettingsRules.assert_can_read(actor)
        total, events = await self._repo.list_page(filters)
        return total, [SecurityEventMapper.to_result(e) for e in events]
