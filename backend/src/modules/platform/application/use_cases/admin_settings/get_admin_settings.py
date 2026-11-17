"""
The settings audit log. Requires read:settings permission.
"""

from src.modules.platform.application.dto.admin_settings_dto.audit import (
    AdminSettingsAuditEntryResult,
)
from src.modules.platform.application.mappers.admin_settings_mapper.audit import AuditEntryMapper
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.services.settings_rules import SettingsRules
from src.modules.platform.ports.outbound.platform_settings_repository import (
    AdminSettingsAuditFilterDto,
)
from src.modules.platform.ports.outbound.platform_settings_repository import (
    IPlatformSettingsRepository,
)


def _assert_can_read(actor: User) -> None:
    SettingsRules.assert_can_read(actor)


class GetAdminSettingsAudit:
    def __init__(self, repo: IPlatformSettingsRepository) -> None:
        self._repo = repo

    async def execute(
        self, actor: User, filters: AdminSettingsAuditFilterDto
    ) -> tuple[int, list[AdminSettingsAuditEntryResult]]:
        _assert_can_read(actor)
        total, entries = await self._repo.get_audit(filters)
        return total, [AuditEntryMapper.audit_to_result(e) for e in entries]
