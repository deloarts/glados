"""
Sends a mail the user composed. Gated on Permission.SEND_MAIL and
rate-limited via mail_policy.py, see CustomMail for why: this dispatches
arbitrary user-composed HTML to an arbitrary recipient through the
instance's own SMTP account, so an unpermissioned or unthrottled version of
this endpoint is an open relay.
"""

from src.modules.platform.application.services.custom_mail import CustomMail
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.value_objects.mail_attachment import MailAttachment
from src.modules.platform.ports.outbound.login_attempt_tracker_port import ILoginAttemptTracker
from src.modules.platform.ports.outbound.mail_service_port import IMailService
from src.modules.platform.ports.outbound.platform_settings_repository import (
    IPlatformSettingsRepository,
)


class SendMail:
    def __init__(
        self,
        mail_service: IMailService,
        rate_tracker: ILoginAttemptTracker,
        settings_repo: IPlatformSettingsRepository,
    ) -> None:
        self._custom = CustomMail(mail_service, rate_tracker, settings_repo)

    async def execute(
        self,
        actor: User,
        to: str,
        subject: str,
        html_body: str,
        cc: str | None = None,
        reply_to: str | None = None,
        attachments: list[MailAttachment] | None = None,
    ) -> None:
        await self._custom.send(
            actor,
            to=to,
            subject=subject,
            html_body=html_body,
            cc=cc,
            reply_to=reply_to,
            attachments=attachments,
        )
