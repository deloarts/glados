"""Jinja2-based template rendering for mail templates. Provides separate
environments for file-based, app-shipped templates and string-based,
admin-configured templates, each with the autoescape setting appropriate
to its source.
"""

import re
from pathlib import Path
from typing import Any

from jinja2 import Environment
from jinja2 import FileSystemLoader
from jinja2 import select_autoescape
from jinja2.sandbox import SandboxedEnvironment

_TEMPLATES_DIR = Path(__file__).parent / "templates"
_TITLE_PATTERN = re.compile(r"<title>(.*?)</title>", re.IGNORECASE | re.DOTALL)

_env = Environment(
    loader=FileSystemLoader(_TEMPLATES_DIR),
    autoescape=select_autoescape(["html"]),
)

# Second engine for DB-stored, admin-authored templates (the welcome/
# notification-digest/test-mail bodies edited in the admin UI, see
# render_string below). `autoescape=True` explicitly, NOT
# `select_autoescape`: that helper picks by template *name*, and a
# `from_string` template has none, so it silently lands on `default=False`
# and stops escaping every interpolated value. Getting this wrong turns
# every stored template into an injection sink for whatever e.g.
# `{{ full_name }}` contains.
# Sandboxed because the source is admin-authored text stored in the
# database, not a file shipped with the repo, and the notification digest
# template runs a `{% for %}` loop over it.
_string_env = SandboxedEnvironment(autoescape=True)


def render_template(name: str, **ctx: Any) -> str:
    return _env.get_template(name).render(**ctx)


def render_string(source: str, **ctx: Any) -> str:
    return _string_env.from_string(source).render(**ctx)


def packaged_template_exists(name: str) -> bool:
    return (_TEMPLATES_DIR / name).is_file()


def packaged_title(name: str) -> str:
    """The `<title>` of a packaged template file, the subject its mail is
    sent with, or "" when the file has none."""
    match = _TITLE_PATTERN.search((_TEMPLATES_DIR / name).read_text(encoding="utf-8"))
    return match.group(1).strip() if match else ""
