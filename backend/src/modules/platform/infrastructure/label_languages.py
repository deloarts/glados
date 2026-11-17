"""
The languages the current request shows localized master-data labels in,
wherever a label has to become one string: the pat API for the SolidWorks
add-in, MCP tools, and the descriptors the server composes from a label
(an order line's "material | type", a search hit's text). A surface-wide
dependency sets them once per request: the web and MCP surfaces use the
acting user's language, the pat surface the add-in language from the PDM
settings, each followed by the tenant's default language. Responses that
carry the label itself still return the whole language map on the web
surface, so the frontend can switch language without reloading.

It is a context variable because FastAPI awaits an async dependency in the
same context as the endpoint and its response validation. Outside a request
the tuple is empty and a label resolves to its first language.
"""

from collections.abc import Iterable
from collections.abc import Mapping
from contextvars import ContextVar

from src.modules.platform.domain.value_objects.localized_text import LocalizedText

_label_languages: ContextVar[tuple[str, ...]] = ContextVar("label_languages", default=())


def set_label_languages(languages: Iterable[str | None]) -> None:
    """Sets the preference order for the rest of the request, dropping
    empty and repeated entries."""
    ordered: list[str] = []
    for language in languages:
        if language and language not in ordered:
            ordered.append(language)
    _label_languages.set(tuple(ordered))


def label_languages() -> tuple[str, ...]:
    return _label_languages.get()


def resolve_label(text: LocalizedText | Mapping[str, str] | None) -> str:
    """`text` in the request's label languages, else in its first language,
    else an empty string."""
    if text is None:
        return ""
    if not isinstance(text, LocalizedText):
        text = LocalizedText(values=text)
    return text.resolve_in(label_languages())
