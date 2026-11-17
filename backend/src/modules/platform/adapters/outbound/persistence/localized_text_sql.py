"""
Query expressions over a JSON column that stores a `LocalizedText` as a map
from language code to text. They are built from SQLAlchemy's generic JSON
element access, which renders as `->>` on Postgres and `JSON_EXTRACT` on
SQLite, so the same query runs in production and in the tests.

A search matches a term in any language, because a user looking for a label
may type it in a language other than their own. A sort key prefers the given
languages in order and then any other language, the same fallback the label
is shown with.
"""

from collections.abc import Sequence
from typing import Any

from sqlalchemy import func
from sqlalchemy import or_

from src.modules.platform.adapters.outbound.persistence.like_escape import contains_ci
from src.modules.platform.domain.value_objects.language import Language


def localized_texts(column: Any) -> list[Any]:
    """The text of `column` in each known language, one expression each, for
    a query that matches or ranks text columns one by one."""
    return [column[code].as_string() for code in Language.values()]


def localized_contains(column: Any, term: str) -> Any:
    """Case-insensitive substring match of `term` against the text of any
    language in `column`."""
    return or_(*(contains_ci(text, term) for text in localized_texts(column)))


def localized_sort_key(column: Any, languages: Sequence[str | None]) -> Any:
    """The text of `column` in the first of `languages` that has one, then
    in any other known language."""
    order: list[str] = []
    for code in [*languages, *Language.values()]:
        if code and code not in order:
            order.append(code)
    return func.coalesce(*(column[code].as_string() for code in order))
