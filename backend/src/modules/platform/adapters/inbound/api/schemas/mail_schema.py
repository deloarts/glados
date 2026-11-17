"""HTTP schemas for email sending and mail template resolution."""

from pydantic import BaseModel
from pydantic import EmailStr
from pydantic import field_validator
from pydantic.networks import validate_email

from src.modules.platform.adapters.inbound.api.schemas.base import ResponseModel
from src.modules.platform.domain.services.mail_recipients import MAX_MAIL_RECIPIENTS
from src.modules.platform.domain.services.mail_recipients import split_mail_recipients


def validated_recipients(value: str, *, required: bool = True) -> str:
    """Checks every address of a recipient text and hands them on as one
    comma separated text. A ValueError, which a field validator answers with
    422, names what is wrong. Other modules' mail schemas use it too."""
    addresses = split_mail_recipients(value)
    if required and not addresses:
        raise ValueError("At least one recipient is needed.")
    if len(addresses) > MAX_MAIL_RECIPIENTS:
        raise ValueError(f"At most {MAX_MAIL_RECIPIENTS} recipients are allowed.")
    return ", ".join(validate_email(address)[1] for address in addresses)


class SendMailRequest(BaseModel):
    # One address, or several separated by commas or semicolons.
    to: str
    subject: str
    html_body: str
    cc: EmailStr | None = None
    reply_to: EmailStr | None = None

    @field_validator("to")
    @classmethod
    def _valid_recipients(cls, value: str) -> str:
        """Checks every address and hands them on as one comma separated
        text, which a ValueError here answers with 422 when one is wrong."""
        return validated_recipients(value)


class DefaultMailTemplateResponse(ResponseModel):
    """The admin default template for one supplier mail kind. It is resolved,
    not stored, so when nothing is configured the answer is a 200 with
    `configured` false and an empty subject and body, not a 404."""

    kind: str
    language: str
    subject: str
    body: str
    configured: bool
