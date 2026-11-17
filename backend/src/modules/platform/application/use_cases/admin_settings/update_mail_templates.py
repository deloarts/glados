"""
Kind-scoped: every language entry for one kind is saved in a single call,
matching the editor dialog's transaction boundary: one audit entry per
save, not one per language row.
"""

from src.modules.platform.application.dto.admin_settings_dto.mail import MailTemplateKindResult
from src.modules.platform.application.dto.admin_settings_dto.mail import UpdateMailTemplatesCommand
from src.modules.platform.application.mappers.admin_settings_mapper.mail import MailSettingsMapper
from src.modules.platform.domain.entities.admin_settings.audit import AdminSettingsAuditEntry
from src.modules.platform.domain.entities.admin_settings.mail import AdminMailTemplate
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.services.settings_rules import SettingsRules
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.ports.outbound.platform_settings_repository import (
    IPlatformSettingsRepository,
)
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork


class UpdateMailTemplates:
    def __init__(self, repo: IPlatformSettingsRepository, *, uow: IUnitOfWork) -> None:
        self._repo = repo
        self._uow = uow

    async def execute(self, actor: User, cmd: UpdateMailTemplatesCommand) -> MailTemplateKindResult:
        SettingsRules.assert_can_write(actor)

        saved = [
            await self._repo.save_mail_template(
                AdminMailTemplate(
                    id=0,
                    kind=cmd.kind,
                    language=entry.language,
                    subject=entry.subject,
                    body=entry.body,
                )
            )
            for entry in cmd.entries
        ]

        # One audit entry for the whole kind-scoped save, not one per
        # language row, keeps the Audit tab readable, see
        # update_mail_settings.py for the same domain="mail" convention.
        await self._repo.append_audit(
            AdminSettingsAuditEntry.by_actor(
                actor,
                settings_domain="mail",
                summary=f"Mail template {cmd.kind.value!r} updated by {actor.username}.",
            )
        )
        await self._uow.commit()

        log.info(f"Updated the {cmd.kind.value!r} mail template.")
        return MailSettingsMapper.mail_template_kind_to_result(cmd.kind, saved)
