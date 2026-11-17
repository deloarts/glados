"""
Uniqueness of the localized names of the labeled catalogue entities (article
groups, source item types, fabrication methods and inspection methods). Two
live rows of one kind must not show the same name in the same language,
ignoring case and surrounding whitespace, because a picker in that language
could not tell them apart. Names in different languages never clash, so a
German name may equal another row's English one.

The rule lives here instead of a unique index because the names are stored
as a JSON map per row, which neither Postgres nor SQLite can index for this.
"""

from collections.abc import Iterable
from dataclasses import dataclass

from src.modules.platform.domain.value_objects.localized_text import LocalizedText


@dataclass(frozen=True)
class NameClash:
    language: str
    text: str
    other_id: int


def find_name_clash(
    entity_id: int, name: LocalizedText, others: Iterable[tuple[int, LocalizedText]]
) -> NameClash | None:
    """The first language in which `name` equals the name of another row in
    `others`, the live rows of the same kind. `entity_id` is skipped, so an
    update does not clash with the row it saves."""
    wanted = {language: text.strip().casefold() for language, text in name.values.items()}
    for other_id, other in others:
        if other_id == entity_id:
            continue
        for language, text in other.values.items():
            if wanted.get(language) == text.strip().casefold():
                return NameClash(language=language, text=name.values[language], other_id=other_id)
    return None
