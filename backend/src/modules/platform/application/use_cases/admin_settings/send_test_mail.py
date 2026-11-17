"""Send a test email through the configured SMTP settings to validate mail delivery."""

from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.exceptions import MailNotConfiguredError
from src.modules.platform.domain.exceptions import MailNotEnabledError
from src.modules.platform.domain.services.settings_rules import SettingsRules
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.ports.outbound.mail_service_port import IMailService
from src.modules.platform.ports.outbound.platform_settings_repository import (
    IPlatformSettingsRepository,
)


class SendTestMail:
    def __init__(
        self,
        settings_repo: IPlatformSettingsRepository,
        mail_service: IMailService,
    ) -> None:
        self._settings = settings_repo
        self._mail = mail_service

    async def execute(self, actor: User, to: str) -> None:
        SettingsRules.assert_can_write(actor)

        mail = await self._settings.get_mail()
        if not mail.enabled:
            raise MailNotEnabledError("Mail is not enabled.")
        if not mail.host or not mail.user or not mail.password:
            raise MailNotConfiguredError("Mail not fully configured.")

        await self._mail.send_test_mail(to)
        log.info("Test mail sent to %s.", to)
