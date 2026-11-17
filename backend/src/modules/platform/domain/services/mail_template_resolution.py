"""
Pure functions over already-loaded AdminMailTemplate entities, with no
repository and no Jinja, so the outbound mail adapter (smtp_mail_service.py)
never needs to import an application-layer service. The fallback chain
this implements:

    recipient's User.language -> tenant default_language -> enGB -> packaged
    file in the repo

The packaged-file floor is not implemented here; it is the caller's
job (smtp_mail_service._render) once `pick_template` returns None, since
only the caller knows where the shipped `<kind>.enGB.html` files live.
"""

from src.modules.platform.domain.entities.admin_settings.mail import AdminMailTemplate
from src.modules.platform.domain.value_objects.language import Language
from src.modules.platform.domain.value_objects.mail_template_kind import MailTemplateKind


def language_preference_order(
    requested: Language | None, tenant_default: Language | None
) -> list[Language]:
    """requested -> tenant default -> Language.default(), missing ones
    dropped, de-duplicated (first occurrence kept, order preserved).

    `tenant_default` is None when `get_general()` raised (unseeded install,
    see IPlatformSettingsRepository).
    """
    seen: set[Language] = set()
    order: list[Language] = []
    for candidate in (requested, tenant_default, Language.default()):
        if candidate is None:
            continue
        if candidate in seen:
            continue
        seen.add(candidate)
        order.append(candidate)
    return order


def pick_template(
    templates: list[AdminMailTemplate], kind: MailTemplateKind, languages: list[Language]
) -> AdminMailTemplate | None:
    """The first template matching `kind` whose body is non-blank, in
    `languages` order. None when nothing configured for `kind` in any of
    those languages; the caller falls through to the packaged file.

    A blank body reads as absent, not as an empty template: a row saved
    without a body must fall through exactly like a missing one, otherwise
    an admin who has translated nothing yet would silently stop everyone's
    mail rather than fall back to English.
    """
    by_language = {t.language: t for t in templates if t.kind == kind}
    for language in languages:
        template = by_language.get(language)
        if template is not None and template.body.strip():
            return template
    return None
