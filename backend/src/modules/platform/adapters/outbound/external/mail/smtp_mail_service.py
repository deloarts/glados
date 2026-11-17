"""SMTP-based email delivery for the various mail template kinds (welcome,
notifications, alerts, and more), resolving each send against a language
fallback chain and, where configured, an admin-authored template.
"""

import ssl
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr
from typing import Any

import aiosmtplib

from src.modules.platform.adapters.outbound.external.mail.render import packaged_template_exists
from src.modules.platform.adapters.outbound.external.mail.render import packaged_title
from src.modules.platform.adapters.outbound.external.mail.render import render_string
from src.modules.platform.adapters.outbound.external.mail.render import render_template
from src.modules.platform.domain.entities.admin_settings.mail import AdminMailSettings
from src.modules.platform.domain.entities.email_notification import EmailNotification
from src.modules.platform.domain.exceptions import SmtpDeliveryError
from src.modules.platform.domain.services.mail_recipients import split_mail_recipients
from src.modules.platform.domain.services.mail_template_resolution import language_preference_order
from src.modules.platform.domain.services.mail_template_resolution import pick_template
from src.modules.platform.domain.services.mail_template_specs import MAIL_TEMPLATE_SPECS
from src.modules.platform.domain.value_objects.language import Language
from src.modules.platform.domain.value_objects.mail_attachment import MailAttachment
from src.modules.platform.domain.value_objects.mail_template_kind import MailTemplateKind
from src.modules.platform.infrastructure.config.settings import cfg
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.ports.outbound.platform_settings_repository import (
    IPlatformSettingsRepository,
)
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork

# Bounds connect and every SMTP command, so an unresponsive mail server fails
# the send (surfacing as SmtpDeliveryError) instead of blocking its caller.
_SMTP_TIMEOUT_SECONDS = 30


def custom_message(html_body: str, attachments: list[MailAttachment]) -> MIMEMultipart:
    """The body of a composed mail: the HTML alone, or a mixed message with
    the HTML first and each attachment after it under its file name."""
    if not attachments:
        message = MIMEMultipart("alternative")
        message.attach(MIMEText(html_body, "html", "utf-8"))
        return message
    message = MIMEMultipart("mixed")
    message.attach(MIMEText(html_body, "html", "utf-8"))
    for attachment in attachments:
        maintype, _, subtype = attachment.content_type.partition("/")
        if not maintype or not subtype:
            maintype, subtype = "application", "octet-stream"
        part = MIMEBase(maintype, subtype)
        part.set_payload(attachment.data)
        encoders.encode_base64(part)
        part.add_header("Content-Disposition", "attachment", filename=attachment.file_name)
        message.attach(part)
    return message


class SmtpMailService:
    def __init__(
        self,
        mail: AdminMailSettings,
        settings_repo: IPlatformSettingsRepository | None = None,
        domain: str | None = None,
        uow: IUnitOfWork | None = None,
    ) -> None:
        self._mail = mail
        # Without it, _render uses the packaged template files only.
        self._settings_repo = settings_repo
        self._domain = domain if domain is not None else cfg.domain
        # Set only on the request path, whose callers send after their own
        # writes are committed. Committing before the SMTP dialogue ends the
        # read transaction the template lookup opened, so the connection goes
        # back to the pool for the up to 30 seconds the mail server may take.
        self._uow = uow

    async def send_welcome(
        self,
        email: str,
        full_name: str,
        username: str,
        created_by_name: str,
        created_by_email: str,
        language: Language | None = None,
    ) -> None:
        log.info("Sending welcome email to %r (%s).", email, full_name)
        subject, body = await self._render(
            MailTemplateKind.WELCOME,
            language,
            full_name=full_name,
            username=username,
            created_by_name=created_by_name,
            created_by_email=created_by_email,
        )
        await self._send(to=email, subject=subject, body=body)
        log.debug("Welcome email delivered to %r.", email)

    async def send_schedule_error(self, task_name: str, message: str) -> None:
        log.warning("Schedule error notification for task %r: %s", task_name, message)
        await self._send_alert(
            MailTemplateKind.SCHEDULE_ERROR, task_name=task_name, message=message
        )

    async def send_disc_space_warning(self, used_gb: float, total_gb: float) -> None:
        log.warning("Disk space warning: %.1f GB used of %.1f GB total.", used_gb, total_gb)
        await self._send_alert(
            MailTemplateKind.DISK_SPACE_WARNING, used_gb=used_gb, total_gb=total_gb
        )

    async def send_system_mail(
        self,
        kind: MailTemplateKind,
        to: str,
        language: Language | None = None,
        **ctx: str,
    ) -> None:
        log.info("Sending %s email to %r.", kind.value, to)
        subject, body = await self._render(kind, language, **ctx)
        await self._send(to=to, subject=subject, body=body)
        log.debug("%s email delivered to %r.", kind.value, to)

    async def send_custom(
        self,
        to: str,
        subject: str,
        html_body: str,
        cc: str | None = None,
        reply_to: str | None = None,
        attachments: list[MailAttachment] | None = None,
    ) -> None:
        log.info(
            "Sending custom email to %r (cc=%r), subject=%r, %d attachment(s).",
            to,
            cc,
            subject,
            len(attachments or []),
        )
        sender = self._mail.from_address or self._mail.user
        msg = custom_message(html_body, attachments or [])
        msg["Subject"] = subject
        msg["From"] = self._from_header(sender)
        msg["To"] = to
        if cc:
            msg["Cc"] = cc
        # The caller's reply_to wins over the configured default.
        effective_reply_to = reply_to if reply_to is not None else self._mail.reply_to
        if effective_reply_to:
            msg["Reply-To"] = effective_reply_to

        recipients = split_mail_recipients(to) + (split_mail_recipients(cc) if cc else [])
        if self._uow is not None:
            await self._uow.commit()
        try:
            async with self._smtp() as smtp:
                await smtp.sendmail(sender, recipients, msg.as_string())
        except (aiosmtplib.SMTPException, OSError) as exc:
            log.warning("Failed to send custom email to %r: %s", to, exc)
            raise SmtpDeliveryError(str(exc)) from exc
        log.debug("Custom email delivered to %r.", to)

    async def send_notification_digest(
        self,
        to: str,
        full_name: str,
        items: list[EmailNotification],
        language: Language | None = None,
    ) -> None:
        log.info("Sending notification digest to %r (%d item(s)).", to, len(items))
        subject, body = await self._render(
            MailTemplateKind.NOTIFICATION_DIGEST,
            language,
            full_name=full_name,
            items=items,
        )
        await self._send(to=to, subject=subject, body=body)
        log.debug("Notification digest delivered to %r.", to)

    async def send_test_mail(self, to: str) -> None:
        log.debug("Sending test mail to %r.", to)
        # A test send has no recipient language, so the tenant default applies.
        subject, body = await self._render(MailTemplateKind.TEST_MAIL, None)
        await self._send(to=to, subject=subject, body=body)
        log.debug("Test mail delivered to %r.", to)

    # ── Private ───────────────────────────────────────────────────────

    async def _tenant_default_language(self) -> Language | None:
        if self._settings_repo is None:
            return None
        try:
            return (await self._settings_repo.get_general()).default_language
        except RuntimeError:
            # An unseeded install falls back to enGB instead of failing.
            return None

    async def _render(
        self, kind: MailTemplateKind, language: Language | None, **ctx: Any
    ) -> tuple[str, str]:
        """Renders through the fallback chain: a stored template in the
        recipient language, the tenant default or enGB, then the packaged file
        in the same language order. `domain` is always in the
        context. The body is never sanitized, since the sanitizer would gut a
        full document and system templates come from files or admins only.
        """
        ctx = {**ctx, "domain": self._domain}
        spec = MAIL_TEMPLATE_SPECS[kind]

        template = None
        if self._settings_repo is not None:
            languages = language_preference_order(language, await self._tenant_default_language())
            templates = await self._settings_repo.list_mail_templates()
            template = pick_template(templates, kind, languages)
        else:
            languages = language_preference_order(language, None)

        if template is not None:
            subject = render_string(template.subject, **ctx).strip() or spec.default_subject
            body = render_string(template.body, **ctx)
            return subject, body

        # The packaged files are the floor: an install with no stored templates
        # still sends every system mail, in the recipient's language when a
        # file ships for it, and the enGB file always ships.
        for candidate in languages:
            name = f"{kind.value}.{candidate.value}.html"
            if packaged_template_exists(name):
                subject = render_string(packaged_title(name), **ctx).strip()
                return subject or spec.default_subject, render_template(name, **ctx)
        body = render_template(f"{kind.value}.{Language.default().value}.html", **ctx)
        return spec.default_subject, body

    async def _send_alert(self, kind: MailTemplateKind, **ctx: Any) -> None:
        """Sends an ops alert to every configured alert recipient. Best
        effort: a no-op without mail or recipients, since the caller's log
        warning is the guaranteed record, and one failed recipient does not
        stop the others.
        """
        if not self._mail.enabled or not self._mail.alert_recipients:
            return
        subject, body = await self._render(kind, None, **ctx)
        for recipient in self._mail.alert_recipients:
            try:
                await self._send(to=recipient, subject=subject, body=body)
            except SmtpDeliveryError:
                continue

    async def _send(self, to: str, subject: str, body: str) -> None:
        sender = self._mail.from_address or self._mail.user
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = self._from_header(sender)
        msg["To"] = to
        if self._mail.reply_to:
            msg["Reply-To"] = self._mail.reply_to
        msg.attach(MIMEText(body, "html", "utf-8"))

        if self._uow is not None:
            await self._uow.commit()
        try:
            async with self._smtp() as smtp:
                await smtp.sendmail(sender, to, msg.as_string())
        except (aiosmtplib.SMTPException, OSError) as exc:
            log.warning("Failed to send email to %r: %s", to, exc)
            raise SmtpDeliveryError(str(exc)) from exc

    def _from_header(self, sender: str) -> str:
        """The From header, with the configured display name when set."""
        return formataddr((self._mail.from_display_name or None, sender))

    @asynccontextmanager
    async def _smtp(self) -> AsyncIterator[aiosmtplib.SMTP]:
        log.debug(
            "Connecting to SMTP %s:%s (ssl=%s, tls=%s).",
            self._mail.host,
            self._mail.port,
            self._mail.use_ssl,
            self._mail.use_tls,
        )
        ctx = ssl.create_default_context()
        if not self._mail.verify_certificate:
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE

        # start_tls is always explicit: aiosmtplib's default (None) would
        # upgrade opportunistically whenever the server offers STARTTLS,
        # which is not what an admin who left TLS off configured.
        smtp = aiosmtplib.SMTP(
            hostname=self._mail.host,
            port=self._mail.port,
            use_tls=self._mail.use_ssl,
            start_tls=self._mail.use_tls and not self._mail.use_ssl,
            tls_context=ctx,
            timeout=_SMTP_TIMEOUT_SECONDS,
        )
        async with smtp:
            await smtp.login(self._mail.user, self._mail.password or "")
            yield smtp
