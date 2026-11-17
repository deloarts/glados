"""
A pure-Python approximation of Postgres pg_trgm's `similarity(text, text)`
for the SQLite-backed integration suite.

pg_trgm lowercases its input, treats runs of non-alphanumeric characters as
word separators, pads each resulting word with two leading blanks and one
trailing blank, and extracts overlapping three-character trigrams from
every padded word. `similarity()` is then the Jaccard index of the two
strings' trigram sets: |intersection| / |union|.

This is a test-only approximation, not a byte-exact port of pg_trgm's C
implementation. It is registered as a SQLite scalar function by
tests/integration/conftest.py's `_register_sqlite_similarity`, so
`func.similarity(col, term) >= 0.3` (the fuzzy fallback query) runs the
same way against the throwaway SQLite file as it does against Postgres in
production.
"""

import re

_WORD_RE = re.compile(r"[a-z0-9]+")


def _trigrams(value: str) -> set[str]:
    trigrams: set[str] = set()
    for word in _WORD_RE.findall(value.lower()):
        padded = f"  {word} "
        trigrams.update(padded[i : i + 3] for i in range(len(padded) - 2))
    return trigrams


def similarity(a: str | None, b: str | None) -> float | None:
    """Jaccard similarity of `a` and `b`'s trigram sets, in [0.0, 1.0].

    Returns `None` (SQL NULL) when either argument is `None`, mirroring
    pg_trgm's own NULL-in/NULL-out `similarity()`: a WHERE clause
    comparing NULL to a threshold evaluates to NULL, i.e. the row is
    excluded, same as a real Postgres NULL column would be.
    """
    if a is None or b is None:
        return None
    trigrams_a, trigrams_b = _trigrams(a), _trigrams(b)
    if not trigrams_a and not trigrams_b:
        return 1.0
    if not trigrams_a or not trigrams_b:
        return 0.0
    return len(trigrams_a & trigrams_b) / len(trigrams_a | trigrams_b)
