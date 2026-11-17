"""
Renders a DRAFT subject+body (not yet saved) through the sandboxed string
env with the kind's spec sample_context, so a SYSTEM-family kind's preview
is byte-identical to what a real send would produce (see
mail_template_specs.py's module docstring for why SUPPLIER-family kinds
are never previewed this way).

A Jinja syntax error (bad `{% %}`/`{{ }}` markup) or an undefined-variable
access (e.g. `{% for item in items %}` when the draft references a
variable the kind's spec doesn't declare) is translated into
MailTemplateRenderError, mapped to 400 by exception_handlers.py, so the
editor can show the message inline rather than the request 500ing.

`render_fn` is injected (see the endpoint, which passes render.render_string)
rather than imported here: this module lives in the application layer,
which must not depend on src.adapters (see the layered-architecture
import-linter contract, [tool.importlinter] in pyproject.toml), the
sandboxed Jinja environment itself is adapter infrastructure.
"""

from collections.abc import Callable
from typing import Any

from jinja2 import TemplateSyntaxError
from jinja2 import UndefinedError

from src.modules.platform.application.dto.admin_settings_dto.mail import PreviewMailTemplateResult
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.exceptions import MailTemplateRenderError
from src.modules.platform.domain.services.mail_template_specs import MAIL_TEMPLATE_SPECS
from src.modules.platform.domain.services.settings_rules import SettingsRules
from src.modules.platform.domain.value_objects.mail_template_kind import MailTemplateKind


class PreviewMailTemplate:
    def __init__(self, render_fn: Callable[..., str]) -> None:
        self._render_fn: Callable[..., str] = render_fn

    async def execute(
        self, actor: User, kind: MailTemplateKind, subject: str, body: str
    ) -> PreviewMailTemplateResult:
        SettingsRules.assert_can_read(actor)

        sample_context: dict[str, Any] = MAIL_TEMPLATE_SPECS[kind].sample_context
        try:
            rendered_subject = self._render_fn(subject, **sample_context)
            rendered_body = self._render_fn(body, **sample_context)
        except (TemplateSyntaxError, UndefinedError) as exc:
            raise MailTemplateRenderError(str(exc)) from exc

        return PreviewMailTemplateResult(subject=rendered_subject, html=rendered_body)
