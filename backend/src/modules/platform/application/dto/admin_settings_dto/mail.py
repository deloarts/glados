"""
Commands and results for the SMTP mail settings, the test mail and the
localized mail templates.
"""

from pydantic import BaseModel
from pydantic import EmailStr
from pydantic import Field
from pydantic import field_validator

from src.modules.platform.application.dto.base import ResultBase
from src.modules.platform.domain.services.mail_alert_policy import normalise_alert_recipients
from src.modules.platform.domain.services.mail_template_specs import MailTemplateFamily
from src.modules.platform.domain.value_objects.language import Language
from src.modules.platform.domain.value_objects.mail_template_kind import MailTemplateKind


class SendTestMailCommand(BaseModel):
    to: EmailStr


class UpdateMailSettingsCommand(BaseModel):
    enabled: bool
    host: str
    port: int
    user: str
    # None means "keep existing password unchanged"
    password: str | None = None
    from_address: str | None = None
    use_tls: bool = True
    use_ssl: bool = False
    # Omitting the field lands on the secure value (DECISION A-2). Recommend
    # shipping this together with the frontend field that sends it, an old
    # frontend build posting without it would silently switch an opted-out
    # relay to verifying.
    verify_certificate: bool = True
    # "" = no display name, see AdminMailSettings.from_display_name.
    from_display_name: str = Field(default="", max_length=128)
    # None = no default Reply-To, see AdminMailSettings.reply_to.
    reply_to: str | None = None
    send_limit_per_hour: int = Field(default=20, ge=1, le=1000)
    send_lock_minutes: int = Field(default=60, ge=1, le=1440)
    # Ops-alert recipients for the schedule-error/disk-space-warning
    # mails, see AdminMailSettings.alert_recipients.
    alert_recipients: list[str] = []
    # None keeps the stored limit.
    attachment_limit_mb: int | None = Field(default=None, ge=1, le=100)

    @field_validator("alert_recipients")
    @classmethod
    def validate_alert_recipients(cls, v: list[str]) -> list[str]:
        """Mirrored on UpdateMailSettingsRequest per the schema
        package's docstring. ValueError here (inside a field_validator) becomes a
        422 through Pydantic/FastAPI's own validation-error handling, same
        reasoning as UpdateMaintenanceSettingsCommand.validate_allowed_ips
        (maintenance.py)."""
        return normalise_alert_recipients(v)


class AdminMailSettingsResult(ResultBase):
    enabled: bool
    host: str
    port: int
    user: str
    password_configured: bool  # True if a password is stored; actual value never returned
    from_address: str | None
    use_tls: bool
    use_ssl: bool
    verify_certificate: bool
    from_display_name: str
    reply_to: str | None
    send_limit_per_hour: int
    send_lock_minutes: int
    alert_recipients: list[str]
    attachment_limit_mb: int


class MailTemplateEntryCommand(BaseModel):
    language: Language
    subject: str
    body: str


class UpdateMailTemplatesCommand(BaseModel):
    """Kind-scoped: every language entry for one kind is saved together,
    matching the editor dialog's transaction boundary: one audit entry
    per save, not one per language row."""

    kind: MailTemplateKind
    entries: list[MailTemplateEntryCommand]


class AdminMailTemplateResult(ResultBase):
    """One admin_mail_template row. `configured` is derived, defined once
    in MailSettingsMapper.mail_template_to_result: a blank body means
    "not translated", never a template to actually send."""

    kind: MailTemplateKind
    language: Language
    subject: str
    body: str
    configured: bool


class MailTemplateKindResult(BaseModel):
    """One kind's spec metadata (from the MAIL_TEMPLATE_SPECS registry)
    plus whatever rows are actually stored for it, across however many
    languages have been saved. A language never saved for this kind simply
    has no entry here. The caller (AdminSettingsTabMail.vue) materializes
    the full kind x language grid client-side from hostStore.languages."""

    kind: MailTemplateKind
    family: MailTemplateFamily
    variables: tuple[str, ...]
    default_subject: str
    entries: list[AdminMailTemplateResult]


class AdminMailTemplatesResult(BaseModel):
    kinds: list[MailTemplateKindResult]


class PreviewMailTemplateCommand(BaseModel):
    """A draft subject+body, not yet saved."""

    subject: str
    body: str


class PreviewMailTemplateResult(BaseModel):
    subject: str
    html: str


class ResolvedMailTemplateResult(BaseModel):
    """The outcome of resolving one (kind, language) pair through the
    fallback chain of mail_template_resolution.py. A resolution, not a stored row, so it can answer
    "nothing configured anywhere" via `configured=False` with an empty
    subject/body, rather than a 404."""

    kind: str
    language: str  # the language actually used, after the fallback chain
    subject: str
    body: str
    configured: bool
