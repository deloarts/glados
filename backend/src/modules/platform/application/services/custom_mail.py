"""
Sends a mail a user composed, for SendMail and for the modules that send
composed mails of their own, such as the meeting notes. Gated on
Permission.SEND_MAIL and rate limited through mail_policy.py, since it
dispatches arbitrary user-composed HTML to arbitrary recipients through the
instance's own SMTP account: an unpermissioned or unthrottled version is an
open relay. Attachments are held to the admin size limit.
"""

from collections.abc import Sequence

from src.modules.platform.application.services.mail_html_sanitizer import sanitize_mail_html
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.exceptions import InsufficientPermissionsError
from src.modules.platform.domain.exceptions import MailRateLimitedError
from src.modules.platform.domain.services.mail_attachment_policy import assert_attachments_fit
from src.modules.platform.domain.services.mail_policy import mail_rate_exceeded
from src.modules.platform.domain.value_objects.mail_attachment import MailAttachment
from src.modules.platform.domain.value_objects.permission import Permission
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.ports.outbound.login_attempt_tracker_port import ILoginAttemptTracker
from src.modules.platform.ports.outbound.mail_service_port import IMailService
from src.modules.platform.ports.outbound.platform_settings_repository import (
    IPlatformSettingsRepository,
)


def _rate_limit_key(actor: User) -> str:
    return f"mail:{actor.id}"


class CustomMail:
    def __init__(
        self,
        mail_service: IMailService,
        rate_tracker: ILoginAttemptTracker,
        settings_repo: IPlatformSettingsRepository,
    ) -> None:
        self._mail = mail_service
        self._rate_tracker = rate_tracker
        self._settings = settings_repo

    @staticmethod
    def assert_can_send(actor: User) -> None:
        if not actor.has_permission(Permission.SEND_MAIL):
            raise InsufficientPermissionsError(
                f"User #{actor.id} ({actor.full_name}) cannot send mail."
            )

    async def assert_attachments_fit(self, files: Sequence[tuple[str, int]]) -> None:
        """Refuses files, each given by name and size in bytes, whose total
        size is over the admin limit, before anyone reads them."""
        assert_attachments_fit(files, (await self._settings.get_mail()).attachment_limit_mb)

    async def send(
        self,
        actor: User,
        to: str,
        subject: str,
        html_body: str,
        cc: str | None = None,
        reply_to: str | None = None,
        attachments: list[MailAttachment] | None = None,
    ) -> None:
        """Sends the mail, or raises when the actor may not send mail, has
        sent too many, the attachments are too large or the mail server
        refuses the mail (SmtpDeliveryError)."""
        self.assert_can_send(actor)
        if attachments:
            await self.assert_attachments_fit([(a.file_name, a.size) for a in attachments])
        await self._assert_within_rate_limit(actor)

        log.info("Sending custom email to %r, subject=%r.", to, subject)
        # Only a mail with attachments names them, so a mail service without
        # attachment support still sends plain mails.
        extra = {"attachments": attachments} if attachments else {}
        await self._mail.send_custom(
            to=to,
            subject=subject,
            html_body=sanitize_mail_html(html_body),
            cc=cc,
            reply_to=reply_to,
            **extra,
        )

    async def _assert_within_rate_limit(self, actor: User) -> None:
        key = _rate_limit_key(actor)

        # Already over the limit from an earlier send in this window,
        # reject without incrementing further, same pre-check shape as
        # the login lockout check before the password is even looked at.
        locked_for = await self._rate_tracker.lock_ttl(key)
        if locked_for > 0:
            log.warning("Rate-limited from sending mail (%ss remaining).", locked_for)
            raise MailRateLimitedError("Mail send rate limit exceeded. Try again later.")

        mail_settings = await self._settings.get_mail()
        limit = mail_settings.send_limit_per_hour
        lock_seconds = mail_settings.send_lock_minutes * 60

        count = await self._rate_tracker.record_failure(key)
        if mail_rate_exceeded(count, limit):
            # The send that crosses the limit is rejected too, see
            # mail_policy.mail_rate_exceeded's docstring.
            await self._rate_tracker.lock(key, lock_seconds)
            log.warning(
                "Exceeded the mail send rate limit (%s/hour); locked for %s minute(s).",
                limit,
                mail_settings.send_lock_minutes,
            )
            raise MailRateLimitedError("Mail send rate limit exceeded. Try again later.")
