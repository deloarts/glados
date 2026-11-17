"""
Resolves the tenant-wide admin default mail template for one kind a user
composes from (request/order/order_canceled/meeting_notes), in the caller's preferred
language, following the fallback chain of mail_template_resolution.py:
requested language -> tenant default -> enGB. Authenticated only, deliberately no permission gate:
`read:settings` would make this admin-only, and every ordinary user
composing a supplier mail needs it before ever reaching the send:mail-
gated send step. See the endpoint (GET /mail/templates/default), which
restricts `kind` to a Literal of those kinds so another system-family body
never reaches a non-admin this way.
"""

from src.modules.platform.application.dto.admin_settings_dto.mail import ResolvedMailTemplateResult
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.services.mail_template_resolution import language_preference_order
from src.modules.platform.domain.services.mail_template_resolution import pick_template
from src.modules.platform.domain.value_objects.language import Language
from src.modules.platform.domain.value_objects.mail_template_kind import MailTemplateKind
from src.modules.platform.ports.outbound.platform_settings_repository import (
    IPlatformSettingsRepository,
)


class GetDefaultMailTemplate:
    def __init__(self, repo: IPlatformSettingsRepository) -> None:
        self._repo = repo

    async def execute(
        self, actor: User, kind: str, language: str | None
    ) -> ResolvedMailTemplateResult:
        tenant_default: Language | None
        try:
            tenant_default = (await self._repo.get_general()).default_language
        except RuntimeError:
            # Unseeded install (get_general raises rather than invent a
            # default, see IPlatformSettingsRepository's docstring); fall
            # through to the fixed floor rather than 500ing a compose
            # screen over a startup-ordering detail.
            tenant_default = None

        # The query parameter is free text: a language no member names
        # matches no template, so it simply drops out of the chain.
        requested = Language(language) if language in Language.values() else None
        languages = language_preference_order(requested, tenant_default)
        template = pick_template(
            await self._repo.list_mail_templates(), MailTemplateKind(kind), languages
        )

        if template is None:
            return ResolvedMailTemplateResult(
                kind=kind,
                language=Language.default().value,
                subject="",
                body="",
                configured=False,
            )

        return ResolvedMailTemplateResult(
            kind=kind,
            language=template.language.value,
            subject=template.subject,
            body=template.body,
            configured=True,
        )
