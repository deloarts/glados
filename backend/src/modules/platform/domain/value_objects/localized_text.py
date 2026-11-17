"""
A label that users maintain in several UI languages at once, for master
data that is entered by hand instead of shipped as translation keys. It is
stored as one map from language code to text, so adding a language never
needs a new column, and an entry that only has some of its languages filled
in still shows something in every language through the fallback in
`resolve`.
"""

from collections.abc import Iterable
from collections.abc import Mapping
from dataclasses import dataclass
from dataclasses import field

from src.modules.platform.domain.exceptions import LocalizedTextInvalidError
from src.modules.platform.domain.value_objects.language import Language


@dataclass(frozen=True)
class LocalizedText:
    """Text per language code. Empty and whitespace-only values are dropped
    on construction, so a language is either present with real text or
    absent."""

    values: Mapping[str, str] = field(default_factory=dict)

    @classmethod
    def of(cls, raw: Mapping[str, str] | None) -> "LocalizedText":
        """Normalises user input: trims every value, drops empty ones and
        rejects language codes the application does not know."""
        known = set(Language.values())
        cleaned: dict[str, str] = {}
        for language, text in (raw or {}).items():
            if language not in known:
                raise LocalizedTextInvalidError(f"Unknown language {language!r} in a label.")
            stripped = text.strip()
            if stripped:
                cleaned[language] = stripped
        return cls(values=cleaned)

    def is_empty(self) -> bool:
        return not self.values

    def has(self, language: str) -> bool:
        return language in self.values

    def resolve(self, language: str, default_language: str) -> str:
        """The text in `language`, else in `default_language`, else the
        first language that has one, else an empty string."""
        for candidate in (language, default_language):
            if candidate in self.values:
                return self.values[candidate]
        return next(iter(self.values.values()), "")

    def resolve_in(self, languages: Iterable[str]) -> str:
        """The text in the first of `languages` that has one, else in the
        first language that has one, else an empty string. `resolve` is the
        common case of a user language followed by the default language."""
        for candidate in languages:
            if candidate in self.values:
                return self.values[candidate]
        return next(iter(self.values.values()), "")

    def as_dict(self) -> dict[str, str]:
        return dict(self.values)


def require_language(text: LocalizedText, language: str, what: str) -> None:
    """Rejects a label that has no text in `language`, which is the
    instance's default language when called from a create or update."""
    if not text.has(language):
        raise LocalizedTextInvalidError(f"The {what} needs a text in the default language.")
