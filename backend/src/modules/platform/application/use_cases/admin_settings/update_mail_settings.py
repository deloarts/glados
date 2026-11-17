"""
Password field: None means "keep existing". A non-None value replaces the stored password.
The attachment limit works the same way: None keeps the stored limit.
"""

from src.modules.platform.application.dto.admin_settings_dto.mail import AdminMailSettingsResult
from src.modules.platform.application.dto.admin_settings_dto.mail import UpdateMailSettingsCommand
from src.modules.platform.application.mappers.admin_settings_mapper.mail import MailSettingsMapper
from src.modules.platform.domain.entities.admin_settings.audit import AdminSettingsAuditEntry
from src.modules.platform.domain.entities.admin_settings.mail import AdminMailSettings
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.services.settings_rules import SettingsRules
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.ports.outbound.platform_settings_repository import (
    IPlatformSettingsRepository,
)
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork


class UpdateMailSettings:
    def __init__(self, repo: IPlatformSettingsRepository, *, uow: IUnitOfWork) -> None:
        self._repo = repo
        self._uow = uow

    async def execute(self, actor: User, cmd: UpdateMailSettingsCommand) -> AdminMailSettingsResult:
        SettingsRules.assert_can_write(actor)

        current = await self._repo.get_mail()
        # Keep the stored password if the caller did not supply a new one.
        password = cmd.password if cmd.password is not None else current.password

        settings = AdminMailSettings(
            id=1,
            enabled=cmd.enabled,
            host=cmd.host,
            port=cmd.port,
            user=cmd.user,
            password=password,
            from_address=cmd.from_address,
            use_tls=cmd.use_tls,
            use_ssl=cmd.use_ssl,
            verify_certificate=cmd.verify_certificate,
            from_display_name=cmd.from_display_name,
            reply_to=cmd.reply_to,
            send_limit_per_hour=cmd.send_limit_per_hour,
            send_lock_minutes=cmd.send_lock_minutes,
            alert_recipients=cmd.alert_recipients,
            attachment_limit_mb=(
                cmd.attachment_limit_mb
                if cmd.attachment_limit_mb is not None
                else current.attachment_limit_mb
            ),
        )
        saved = await self._repo.save_mail(settings)

        await self._repo.append_audit(
            AdminSettingsAuditEntry.by_actor(
                actor,
                settings_domain="mail",
                summary=f"Mail settings updated by {actor.username}.",
            )
        )
        await self._uow.commit()

        log.info("Updated mail settings.")
        return MailSettingsMapper.mail_to_result(saved)
