"""
User-initiated mail send. The frontend composes the mail (TO, CC, subject,
HTML body) and POSTs it here; the backend dispatches via SMTP.
"""

from typing import Literal

from fastapi import Depends
from fastapi import status
from fastapi.routing import APIRouter

from src.modules.platform.adapters.inbound.api.auth_deps import get_current_active_user
from src.modules.platform.adapters.inbound.api.deps.misc import get_default_mail_template_use_case
from src.modules.platform.adapters.inbound.api.deps.misc import get_send_mail_use_case
from src.modules.platform.adapters.inbound.api.schemas.mail_schema import (
    DefaultMailTemplateResponse,
)
from src.modules.platform.adapters.inbound.api.schemas.mail_schema import SendMailRequest
from src.modules.platform.application.dto.admin_settings_dto.mail import ResolvedMailTemplateResult
from src.modules.platform.application.use_cases.mail.get_default_mail_template import (
    GetDefaultMailTemplate,
)
from src.modules.platform.application.use_cases.mail.send_mail import SendMail
from src.modules.platform.domain.entities.user import User

router = APIRouter()


@router.post("/send", status_code=status.HTTP_204_NO_CONTENT)
async def send_mail(
    body: SendMailRequest,
    actor: User = Depends(get_current_active_user),
    use_case: SendMail = Depends(get_send_mail_use_case),
) -> None:
    """Send a user-composed HTML email via SMTP. Requires send:mail and is
    rate-limited per sender."""
    await use_case.execute(
        actor=actor,
        to=str(body.to),
        subject=body.subject,
        html_body=body.html_body,
        cc=str(body.cc) if body.cc else None,
        reply_to=str(body.reply_to) if body.reply_to else None,
    )


@router.get("/templates/default", response_model=DefaultMailTemplateResponse)
async def get_default_mail_template(
    kind: Literal["request", "order", "order_canceled", "meeting_notes"],
    language: str | None = None,
    actor: User = Depends(get_current_active_user),
    use_case: GetDefaultMailTemplate = Depends(get_default_mail_template_use_case),
) -> ResolvedMailTemplateResult:
    """Resolve the tenant-wide admin default template for one SUPPLIER-
    family kind or the meeting notes mail, in the requested (or
    tenant-default, or enGB) language. The meeting notes body is a fragment
    with `{{ var }}` placeholders, filled in by the compose dialog like the
    supplier kinds.

    Authenticated only, no permission gate: any user composing a supplier
    mail needs this, not just an admin. `send:mail` belongs at the send
    step, not at compose time. `kind` is deliberately a `Literal` of the
    kinds a user composes from, not `MailTemplateKind`, so another SYSTEM-
    family body (e.g. `welcome`'s HTML) can never reach a non-admin
    through this endpoint.
    """
    return await use_case.execute(actor=actor, kind=kind, language=language)
