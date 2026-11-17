"""
Made-item revision strings: two
schemes only, inferred from the current value rather than configured per
item: `0`, `1`, `2`, ... (numeric) or `A`, `B`, ... `Z`, `AA`, `AB`, ...
(bijective base-26 upper-case, the same counting scheme spreadsheet column
letters use, so `Z` rolls to `AA` rather than overflowing a fixed width).
No I/O, no admin-settings reads; callers (the web "New revision" flow and,
later, PDM ingest) resolve `skip_ambiguous` from settings
themselves and pass it in.
"""

import re
from enum import Enum
from enum import unique

from src.modules.catalogue.domain.errors import RevisionNotIncrementableError

_NUMERIC_RE = re.compile(r"^\d+$")
_ALPHA_RE = re.compile(r"^[A-Z]+$")

# ASME Y14.35 letter skipping: these five are easily mistaken for a
# digit or for each other (I/1, O/0, Q/O, S/5, X/multiplication, Z/2) and
# are excluded from the alphabet when the admin setting is on, leaving a
# 20-letter bijective base instead of the usual 26.
_AMBIGUOUS_LETTERS = frozenset("IOQSXZ")
_FULL_ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
_SKIP_ALPHABET = "".join(c for c in _FULL_ALPHABET if c not in _AMBIGUOUS_LETTERS)

# The numbering-tab Select offers exactly these three start values,
# default "0" (validated by UpdateMadeItemSettings against this tuple).
START_REVISIONS = ("A", "0", "1")


@unique
class RevisionScheme(str, Enum):
    NUMERIC = "NUMERIC"
    ALPHA = "ALPHA"


def detect(rev: str) -> RevisionScheme | None:
    """Infers the scheme from the current revision string alone: digits
    only -> NUMERIC, upper-case letters only -> ALPHA, anything else
    (empty, mixed, lower-case, punctuation) -> None, meaning "cannot be
    incremented"."""
    if _NUMERIC_RE.match(rev):
        return RevisionScheme.NUMERIC
    if _ALPHA_RE.match(rev):
        return RevisionScheme.ALPHA
    return None


def _increment_bijective(value: str, alphabet: str) -> str:
    """Increments a bijective base-len(alphabet) numeral (each position is
    a digit 1..N, never a 0 digit) written in `alphabet`'s order, carrying
    left the same way spreadsheet column letters do: the last letter of
    the alphabet wraps to the first and carries, so "Z" (or, in skip mode,
    the alphabet's last letter) becomes "AA" rather than growing a 0."""
    digits = list(value)
    index_of = {c: i for i, c in enumerate(alphabet)}
    position = len(digits) - 1
    while position >= 0:
        digit_index = index_of[digits[position]]
        if digit_index + 1 < len(alphabet):
            digits[position] = alphabet[digit_index + 1]
            return "".join(digits)
        digits[position] = alphabet[0]
        position -= 1
    return alphabet[0] + "".join(digits)


def next_revision(rev: str, skip_ambiguous: bool = False) -> str:
    """Returns the next revision after `rev` in its own scheme:
    numeric increments by 1 with no padding ("9" -> "10"); alpha increments
    the letters bijectively ("Z" -> "AA", "AZ" -> "BA"). `skip_ambiguous`
    increments over the 20-letter alphabet with I/O/Q/S/X/Z removed
    instead of the full 26; `rev` containing one of those letters is a
    contradiction (the setting was presumably turned on after the fact) and
    is rejected rather than silently ignored.

    Raises RevisionNotIncrementableError (409) for anything detect() can't
    place in a scheme, and for a skipped letter under skip_ambiguous."""
    scheme = detect(rev)
    if scheme is None:
        raise RevisionNotIncrementableError(
            f"Revision {rev!r} is neither purely numeric nor purely alphabetic "
            "(A-Z) and cannot be incremented."
        )

    if scheme is RevisionScheme.NUMERIC:
        return str(int(rev) + 1)

    if skip_ambiguous:
        ambiguous = sorted(set(rev) & _AMBIGUOUS_LETTERS)
        if ambiguous:
            raise RevisionNotIncrementableError(
                f"Revision {rev!r} contains letter(s) {ambiguous} excluded by the "
                "'skip ambiguous letters' setting and cannot be incremented."
            )
        return _increment_bijective(rev, _SKIP_ALPHABET)

    return _increment_bijective(rev, _FULL_ALPHABET)


def sort_key(rev: str) -> tuple[int, str]:
    """ "Newest" ordering: longer beats shorter ("9" < "10"), then
    lexicographic within the same length ("Z" < "AA" holds only because
    length already separates them; within one length plain string order
    matches both schemes). Used identically in SQL (order by length(x)
    then x) and here, so the two never disagree on which revision is
    newest."""
    return (len(rev), rev)
