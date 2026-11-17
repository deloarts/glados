"""
Abstract mail interface. The application layer calls this, never
the SMTP implementation directly.
"""

from typing import Protocol
from typing import runtime_checkable

from src.modules.platform.domain.entities.email_notification import EmailNotification
from src.modules.platform.domain.value_objects.language import Language
from src.modules.platform.domain.value_objects.mail_attachment import MailAttachment
from src.modules.platform.domain.value_objects.mail_template_kind import MailTemplateKind


@runtime_checkable
class IMailService(Protocol):
    async def send_welcome(
        self,
        email: str,
        full_name: str,
        username: str,
        created_by_name: str,
        created_by_email: str,
        language: Language | None = None,
    ) -> None:
        """Send a welcome mail to a newly created user.

        Never carries the password: the account's creator (created_by_*)
        is named instead, so the new user asks them for it out of band
        rather than it ever appearing in plaintext in an inbox.

        `language` is the recipient's own User.language, the first link in
        the fallback chain of mail_template_resolution.py (applied in
        smtp_mail_service._render); None falls straight through to the
        tenant default.
        """
        ...

    async def send_notification_digest(
        self,
        to: str,
        full_name: str,
        items: list[EmailNotification],
        language: Language | None = None,
    ) -> None:
        """Send a digest of queued email notifications to one recipient.

        `language` is the recipient's own User.language, same fallback
        chain as send_welcome above."""
        ...

    async def send_schedule_error(self, task_name: str, message: str) -> None:
        """Log-and-alert: renders `schedule_error` (tenant default
        language) and fans it out to every configured
        mail.alert_recipients address. Silently a no-op when mail is
        disabled or no recipient is configured; the caller's own
        log.warning is the guaranteed record."""
        ...

    async def send_disc_space_warning(self, used_gb: float, total_gb: float) -> None:
        """Same alert-fan-out contract as send_schedule_error above, for
        the `disk_space_warning` kind."""
        ...

    async def send_system_mail(
        self,
        kind: MailTemplateKind,
        to: str,
        language: Language | None = None,
        **ctx: str,
    ) -> None:
        """Generic SYSTEM-family send for the event-driven mails that have
        no bespoke method (account_deactivated, permissions_changed,
        project_assigned, product_assigned; see
        HandleEventNotifications). `ctx` is whatever the kind's template
        needs beyond `full_name`/`domain` (e.g. `project_number`); an
        unknown kind or a missing context variable behaves exactly like
        every other _render call; see smtp_mail_service._render.

        Kept generic rather than four near-identical send_* methods: each
        of the four call sites differs only in `kind` and one extra
        context field, so a bespoke method per kind would be pure
        duplication; see the four call sites in handle_event_notifications.py.
        """
        ...

    async def send_custom(
        self,
        to: str,
        subject: str,
        html_body: str,
        cc: str | None = None,
        reply_to: str | None = None,
        attachments: list[MailAttachment] | None = None,
    ) -> None:
        """Send a user-composed HTML mail to arbitrary recipients. `to` and
        `cc` are one address or several separated by commas. The caller has
        checked the attachments against the size limit. Raises
        SmtpDeliveryError when the mail server refuses the mail."""
        ...

    async def send_test_mail(self, to: str) -> None:
        """Send a connectivity test e-mail to the given address, resolved
        against the tenant's default language (there is no recipient
        preference to read for a test send)."""
        ...
