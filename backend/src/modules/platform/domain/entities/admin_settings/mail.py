"""
Domain entities for outbound mail: the SMTP settings singleton and the
localized, admin-editable mail template rows.
"""

from dataclasses import dataclass

from src.modules.platform.domain.value_objects.language import Language
from src.modules.platform.domain.value_objects.mail_template_kind import MailTemplateKind
from src.shared_kernel.domain.entities.base import Entity


@dataclass
class AdminMailSettings(Entity):
    """Outbound SMTP email configuration."""

    enabled: bool
    host: str
    port: int
    user: str
    # Stored as plaintext, same trust level as env var. Never returned in API responses.
    password: str | None
    from_address: str | None
    use_tls: bool
    use_ssl: bool
    # False disables hostname and chain validation (ssl.CERT_NONE) for an
    # internal relay the system trust store cannot validate; True is the
    # default for new installs. See smtp_mail_service._smtp.
    verify_certificate: bool
    # Display name wrapped around `from_address or user` in the From header
    # (smtp_mail_service._from_header); "" sends the bare address.
    from_display_name: str
    # Reply-To used when a caller supplies none; None sends no Reply-To.
    reply_to: str | None
    # Sends per user within the lock window before further sends are rejected
    # (domain/services/mail_policy.py).
    send_limit_per_hour: int
    # How long, in minutes, a user who crosses send_limit_per_hour is locked
    # out of sending.
    send_lock_minutes: int
    # Ops-alert recipients for the schedule error and disk space warning mails.
    alert_recipients: list[str]
    # The total size, in megabytes, the attachments of one composed mail may
    # have (domain/services/mail_attachment_policy.py).
    attachment_limit_mb: int = 10


@dataclass
class AdminMailTemplate(Entity):
    """One localized, admin-editable mail template, keyed by (kind, language)
    through a unique constraint on the ORM model. `subject` and `body` are ""
    when a pair is not translated, and pick_template
    (domain/services/mail_template_resolution.py) treats a blank body as absent.
    """

    kind: MailTemplateKind
    language: Language
    subject: str
    body: str
