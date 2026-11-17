"""
Returns every MailTemplateKind's spec metadata (family/variables/
default_subject) plus whatever rows are actually stored for it. Kept
separate from GET /admin/settings/ (GetAllAdminSettings), because bodies
are multi-KB and every settings tab fetches that aggregate.
"""

from src.modules.platform.application.dto.admin_settings_dto.mail import AdminMailTemplatesResult
from src.modules.platform.application.mappers.admin_settings_mapper.mail import MailSettingsMapper
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.services.settings_rules import SettingsRules
from src.modules.platform.ports.outbound.platform_settings_repository import (
    IPlatformSettingsRepository,
)


class GetMailTemplates:
    def __init__(self, repo: IPlatformSettingsRepository) -> None:
        self._repo = repo

    async def execute(self, actor: User) -> AdminMailTemplatesResult:
        SettingsRules.assert_can_read(actor)
        return MailSettingsMapper.mail_templates_to_result(await self._repo.list_mail_templates())
