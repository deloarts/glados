"""Use case factories: mail sending and the default supplier mail template,
and public id resolution. Also the tenant's timezone, the one zone every calendar-date filter and
"today" of a request is read in, and the languages a web request sorts
localized labels by.
"""

from datetime import tzinfo

from fastapi import Depends

from src.modules.platform.adapters.inbound.api.auth_deps import get_current_active_user
from src.modules.platform.adapters.inbound.api.deps.database import get_public_id_resolver
from src.modules.platform.adapters.inbound.api.deps.repositories import get_platform_settings_repo
from src.modules.platform.adapters.inbound.api.deps.services import get_login_attempt_tracker
from src.modules.platform.adapters.inbound.api.deps.services import get_mail_service
from src.modules.platform.application.services.custom_mail import CustomMail
from src.modules.platform.application.services.tenant_timezone import tenant_zone
from src.modules.platform.application.use_cases.mail.get_default_mail_template import (
    GetDefaultMailTemplate,
)
from src.modules.platform.application.use_cases.mail.send_mail import SendMail
from src.modules.platform.application.use_cases.resolve.resolve_public_id import ResolvePublicId
from src.modules.platform.domain.entities.user import User
from src.modules.platform.ports.outbound.login_attempt_tracker_port import ILoginAttemptTracker
from src.modules.platform.ports.outbound.mail_service_port import IMailService
from src.modules.platform.ports.outbound.platform_settings_repository import (
    IPlatformSettingsRepository,
)
from src.modules.platform.ports.outbound.repositories.public_id_resolver import IPublicIdResolver


def get_send_mail_use_case(
    mail_service: IMailService = Depends(get_mail_service),
    rate_tracker: ILoginAttemptTracker = Depends(get_login_attempt_tracker),
    settings_repo: IPlatformSettingsRepository = Depends(get_platform_settings_repo),
) -> SendMail:
    return SendMail(
        mail_service=mail_service, rate_tracker=rate_tracker, settings_repo=settings_repo
    )


def get_custom_mail(
    mail_service: IMailService = Depends(get_mail_service),
    rate_tracker: ILoginAttemptTracker = Depends(get_login_attempt_tracker),
    settings_repo: IPlatformSettingsRepository = Depends(get_platform_settings_repo),
) -> CustomMail:
    """Sends the mails users compose in other modules, such as meeting
    notes, under the same permission, rate limit and attachment limit as
    POST /mail/send."""
    return CustomMail(mail_service, rate_tracker, settings_repo)


def get_resolve_public_id_use_case(
    resolver: IPublicIdResolver = Depends(get_public_id_resolver),
) -> ResolvePublicId:
    return ResolvePublicId(resolver=resolver)


def get_default_mail_template_use_case(
    repo: IPlatformSettingsRepository = Depends(get_platform_settings_repo),
) -> GetDefaultMailTemplate:
    return GetDefaultMailTemplate(repo)


async def get_tenant_zone(
    settings_repo: IPlatformSettingsRepository = Depends(get_platform_settings_repo),
) -> tzinfo:
    """The tenant's default timezone from the general settings, the zone a
    request reads its calendar-date filters and its "today" in."""
    return await tenant_zone(settings_repo)


async def get_label_languages(
    actor: User = Depends(get_current_active_user),
    settings_repo: IPlatformSettingsRepository = Depends(get_platform_settings_repo),
) -> tuple[str, ...]:
    """The acting user's language followed by the tenant's default language,
    the order a localized label is shown and sorted in for this user."""
    tenant_default = (await settings_repo.get_general()).default_language
    return tuple(dict.fromkeys([actor.language.value, tenant_default.value]))
