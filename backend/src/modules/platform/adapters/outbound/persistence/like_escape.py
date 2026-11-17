r"""
src/modules/platform/adapters/outbound/persistence/like_escape.py

Escape user-supplied text before it goes into a SQL LIKE/ILIKE pattern.

Values are always bound as parameters, so this is not about SQL injection,
it is about LIKE *wildcard* injection: a raw percent or underscore from a
search box acts as a wildcard, so a search for "50%" silently matches far
more than the literal string, and a term of many percent signs forces an
expensive full-table pattern scan (a mild authenticated DoS on large
tables).

Repositories build a case-insensitive substring match with
`contains_ci(col, term)`, which expands to
`col.ilike(f"%{escape_like(term)}%", escape="\\")`. The explicit
`escape="\\"` tells the database that the backslashes this adds are the
escape character, so the percent, underscore, and backslash characters in
the input match literally.
"""

from typing import Any


def escape_like(term: str) -> str:
    r"""Backslash-escape the LIKE metacharacters (backslash, percent,
    underscore) in `term` so it matches literally inside a `%...%` pattern.
    Pair with `.ilike(..., escape="\\")`."""
    return term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def contains_ci(column: Any, term: str) -> Any:
    """Case-insensitive substring match of `term` against `column`, with
    the LIKE wildcards in the term escaped so they match literally."""
    return column.ilike(f"%{escape_like(term)}%", escape="\\")
