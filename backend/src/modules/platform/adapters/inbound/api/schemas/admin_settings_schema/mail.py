"""
HTTP request and response schemas for the SMTP mail settings, the test mail and
the localized mail templates.
"""

from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import EmailStr
from pydantic import Field
from pydantic import field_validator

from src.modules.platform.adapters.inbound.api.schemas.base import EntityResponse
from src.modules.platform.adapters.inbound.api.schemas.base import ResponseModel
from src.modules.platform.domain.services.mail_alert_policy import normalise_alert_recipients
from src.modules.platform.domain.services.mail_template_specs import MailTemplateFamily
from src.modules.platform.domain.value_objects.language import Language
from src.modules.platform.domain.value_objects.mail_template_kind import MailTemplateKind


class SendTestMailRequest(BaseModel):
    to: EmailStr


class UpdateMailSettingsRequest(BaseModel):
    enabled: bool
    host: str
    port: int
    user: str
    password: str | None = None
    from_address: str | None = None
    use_tls: bool = True
    use_ssl: bool = False
    verify_certificate: bool = True
    # "" = no display name, mirrored on UpdateMailSettingsCommand per this
    # module's docstring.
    from_display_name: str = Field(default="", max_length=128)
    reply_to: str | None = None
    send_limit_per_hour: int = Field(default=20, ge=1, le=1000)
    send_lock_minutes: int = Field(default=60, ge=1, le=1440)
    alert_recipients: list[str] = []
    # Left out, the limit stays as it is.
    attachment_limit_mb: int | None = Field(default=None, ge=1, le=100)

    @field_validator("alert_recipients")
    @classmethod
    def validate_alert_recipients(cls, v: list[str]) -> list[str]:
        """Mirrored on UpdateMailSettingsCommand per the package's
        docstring. ValueError here (inside a field_validator) becomes a
        proper 422, see validate_office_sharepoint_url_scheme (general.py) for
        why that matters versus a bare ValueError inside the use case."""
        return normalise_alert_recipients(v)


class MailTemplateEntryRequest(BaseModel):
    language: Language
    subject: str
    body: str


class UpdateMailTemplatesRequest(BaseModel):
    """`kind` is a path parameter (PUT /mail/templates/{kind}), not part of
    this body: it is the resource being replaced, not a field of it."""

    entries: list[MailTemplateEntryRequest]


class PreviewMailTemplateRequest(BaseModel):
    """A draft subject+body, not yet saved."""

    subject: str
    body: str


class AdminMailSettingsResponse(EntityResponse):
    enabled: bool
    host: str
    port: int
    user: str
    password_configured: bool
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


class AdminMailTemplateResponse(EntityResponse):
    kind: MailTemplateKind
    language: Language
    subject: str
    body: str
    configured: bool


class MailTemplateKindResponse(ResponseModel):
    kind: MailTemplateKind
    family: MailTemplateFamily
    variables: tuple[str, ...]
    default_subject: str
    entries: list[AdminMailTemplateResponse]

    model_config = ConfigDict(from_attributes=True)


class AdminMailTemplatesResponse(ResponseModel):
    kinds: list[MailTemplateKindResponse]

    model_config = ConfigDict(from_attributes=True)


class PreviewMailTemplateResponse(ResponseModel):
    subject: str
    html: str
