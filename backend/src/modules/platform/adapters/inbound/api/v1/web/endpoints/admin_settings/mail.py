"""
Admin settings endpoints for the Mail tab, including mail templates. All
reads require read:settings; all writes require write:settings.
"""

from fastapi import Depends
from fastapi import status
from fastapi.routing import APIRouter

from src.modules.platform.adapters.inbound.api.auth_deps import get_current_active_user
from src.modules.platform.adapters.inbound.api.deps.admin_settings import get_mail_settings_use_case
from src.modules.platform.adapters.inbound.api.deps.admin_settings import (
    get_mail_templates_use_case,
)
from src.modules.platform.adapters.inbound.api.deps.admin_settings import (
    get_preview_mail_template_use_case,
)
from src.modules.platform.adapters.inbound.api.deps.admin_settings import (
    get_send_test_mail_use_case,
)
from src.modules.platform.adapters.inbound.api.deps.admin_settings import (
    get_update_mail_settings_use_case,
)
from src.modules.platform.adapters.inbound.api.deps.admin_settings import (
    get_update_mail_templates_use_case,
)
from src.modules.platform.adapters.inbound.api.schemas.admin_settings_schema.mail import (
    AdminMailSettingsResponse,
)
from src.modules.platform.adapters.inbound.api.schemas.admin_settings_schema.mail import (
    AdminMailTemplatesResponse,
)
from src.modules.platform.adapters.inbound.api.schemas.admin_settings_schema.mail import (
    MailTemplateKindResponse,
)
from src.modules.platform.adapters.inbound.api.schemas.admin_settings_schema.mail import (
    PreviewMailTemplateRequest,
)
from src.modules.platform.adapters.inbound.api.schemas.admin_settings_schema.mail import (
    PreviewMailTemplateResponse,
)
from src.modules.platform.adapters.inbound.api.schemas.admin_settings_schema.mail import (
    SendTestMailRequest,
)
from src.modules.platform.adapters.inbound.api.schemas.admin_settings_schema.mail import (
    UpdateMailSettingsRequest,
)
from src.modules.platform.adapters.inbound.api.schemas.admin_settings_schema.mail import (
    UpdateMailTemplatesRequest,
)
from src.modules.platform.application.dto.admin_settings_dto.mail import AdminMailSettingsResult
from src.modules.platform.application.dto.admin_settings_dto.mail import AdminMailTemplatesResult
from src.modules.platform.application.dto.admin_settings_dto.mail import MailTemplateEntryCommand
from src.modules.platform.application.dto.admin_settings_dto.mail import MailTemplateKindResult
from src.modules.platform.application.dto.admin_settings_dto.mail import PreviewMailTemplateResult
from src.modules.platform.application.dto.admin_settings_dto.mail import UpdateMailSettingsCommand
from src.modules.platform.application.dto.admin_settings_dto.mail import UpdateMailTemplatesCommand
from src.modules.platform.application.use_cases.admin_settings.get_mail_settings import (
    GetMailSettings,
)
from src.modules.platform.application.use_cases.admin_settings.get_mail_templates import (
    GetMailTemplates,
)
from src.modules.platform.application.use_cases.admin_settings.preview_mail_template import (
    PreviewMailTemplate,
)
from src.modules.platform.application.use_cases.admin_settings.send_test_mail import SendTestMail
from src.modules.platform.application.use_cases.admin_settings.update_mail_settings import (
    UpdateMailSettings,
)
from src.modules.platform.application.use_cases.admin_settings.update_mail_templates import (
    UpdateMailTemplates,
)
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.value_objects.mail_template_kind import MailTemplateKind

router = APIRouter()


@router.get("/mail", response_model=AdminMailSettingsResponse)
async def get_mail_settings(
    actor: User = Depends(get_current_active_user),
    use_case: GetMailSettings = Depends(get_mail_settings_use_case),
) -> AdminMailSettingsResult:
    return await use_case.execute(actor=actor)


@router.put("/mail", response_model=AdminMailSettingsResponse)
async def update_mail_settings(
    body: UpdateMailSettingsRequest,
    actor: User = Depends(get_current_active_user),
    use_case: UpdateMailSettings = Depends(get_update_mail_settings_use_case),
) -> AdminMailSettingsResult:
    """Update SMTP / mail settings. Requires write:settings."""
    cmd = UpdateMailSettingsCommand(**body.model_dump())
    return await use_case.execute(actor=actor, cmd=cmd)


@router.post("/mail/test", status_code=status.HTTP_204_NO_CONTENT)
async def send_test_mail(
    body: SendTestMailRequest,
    actor: User = Depends(get_current_active_user),
    use_case: SendTestMail = Depends(get_send_test_mail_use_case),
) -> None:
    """Send a test e-mail to the given address using the stored SMTP config."""
    # SendTestMail raises InsufficientPermissionsError (403),
    # MailNotEnabledError or MailNotConfiguredError (400) and
    # SmtpDeliveryError (502), all mapped in exception_handlers. smtplib and
    # OSError failures are already wrapped in SmtpDeliveryError by
    # SmtpMailService. Anything else is a real bug, not an SMTP failure, so
    # it propagates to UnhandledExceptionMiddleware's generic 500 instead of
    # leaking str(exc) to the client.
    await use_case.execute(actor=actor, to=body.to)


@router.get("/mail/templates", response_model=AdminMailTemplatesResponse)
async def get_mail_templates(
    actor: User = Depends(get_current_active_user),
    use_case: GetMailTemplates = Depends(get_mail_templates_use_case),
) -> AdminMailTemplatesResult:
    """Return every mail-template kind's metadata (family, variables, default
    subject) and the rows stored for it. Requires read:settings."""
    # Not part of GET /admin/settings/: the bodies are several KB and every
    # settings tab fetches that aggregate.
    return await use_case.execute(actor=actor)


@router.put("/mail/templates/{kind}", response_model=MailTemplateKindResponse)
async def update_mail_templates(
    kind: MailTemplateKind,
    body: UpdateMailTemplatesRequest,
    actor: User = Depends(get_current_active_user),
    use_case: UpdateMailTemplates = Depends(get_update_mail_templates_use_case),
) -> MailTemplateKindResult:
    """Replace every language entry for one kind in a single transaction,
    one audit entry, not one per language row. Requires write:settings.
    An unknown `kind` or an unknown `language` inside an entry 422s before
    this ever runs, both are closed Enum types."""
    cmd = UpdateMailTemplatesCommand(
        kind=kind,
        entries=[MailTemplateEntryCommand(**entry.model_dump()) for entry in body.entries],
    )
    return await use_case.execute(actor=actor, cmd=cmd)


@router.post("/mail/templates/{kind}/preview", response_model=PreviewMailTemplateResponse)
async def preview_mail_template(
    kind: MailTemplateKind,
    body: PreviewMailTemplateRequest,
    actor: User = Depends(get_current_active_user),
    use_case: PreviewMailTemplate = Depends(get_preview_mail_template_use_case),
) -> PreviewMailTemplateResult:
    """Render a draft subject and body with the kind's sample values, so a
    system mail's preview is identical to what a real send produces. 400
    when the template has a syntax error or uses an unknown variable.
    Requires read:settings."""
    # No catch-all: PreviewMailTemplate raises only InsufficientPermissionsError
    # and MailTemplateRenderError, both mapped in exception_handlers.
    return await use_case.execute(actor=actor, kind=kind, subject=body.subject, body=body.body)
