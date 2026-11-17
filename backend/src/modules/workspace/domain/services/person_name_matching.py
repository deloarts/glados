"""
Suggests which known person a name written in notes means, such as "Hans
M." or "Müller (customer)", among candidates such as users and contacts.
The suggestion is only a starting point for a person who confirms it, so
it errs on the side of offering nothing: a name counts as matched only
when every word of it fits the candidate, a word in full or a single
letter as the initial of one of the candidate's words, and at least one
word fits in full. An e-mail address the notes carry matches on its own.
Accents, case and punctuation are ignored. No I/O.
"""

import re
import unicodedata
from dataclasses import dataclass
from dataclasses import field
from enum import unique

from src.shared_kernel.domain.value_objects.value_enum import StrValueEnum

# Words that say who someone is rather than name them.
_NOISE = frozenset(
    {"herr", "frau", "hr", "fr", "mr", "mrs", "ms", "dr", "ing", "dipl", "mag", "fa", "firma"}
)
_EMAIL_RE = re.compile(r"[^\s<>()\[\],;]+@[^\s<>()\[\],;]+\.[^\s<>()\[\],;]+")
_SUGGESTIONS_MAX = 3


@unique
class PersonKind(StrValueEnum):
    USER = "user"
    CONTACT = "contact"


@dataclass(frozen=True)
class PersonCandidate:
    kind: PersonKind
    id: int
    name: str
    email: str | None = None
    # Other spellings that name the person on their own, such as a username.
    aliases: tuple[str, ...] = ()


@dataclass(frozen=True)
class PersonMatch:
    written: str
    # The fitting candidates, best first.
    candidates: list[PersonCandidate] = field(default_factory=list)
    # The candidate to preselect: the only one that fits best, if any.
    best: PersonCandidate | None = None


def _fold(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text.casefold())
    return "".join(c for c in decomposed if not unicodedata.combining(c))


def _words(text: str) -> list[str]:
    words = re.split(r"[^0-9a-z]+", _fold(text))
    return [w for w in words if w and w not in _NOISE]


def _score(written: list[str], candidate: PersonCandidate) -> int:
    """How well the written words fit the candidate, 0 when they do not."""
    names = _words(candidate.name)
    if not names:
        return 0
    full = 0
    for word in written:
        if word in names:
            full += 1
        elif len(word) == 1 and any(n.startswith(word) for n in names):
            continue
        else:
            return 0
    if full == 0:
        return 0
    # Every word of the candidate named in full is the strongest fit.
    return full * 10 + (5 if full == len(names) else 0)


def match_person(written: str, candidates: list[PersonCandidate]) -> PersonMatch:
    folded = _fold(written)
    email = _EMAIL_RE.search(folded)
    if email is not None:
        address = email.group(0)
        by_email = [c for c in candidates if c.email and _fold(c.email) == address]
        if len(by_email) == 1:
            return PersonMatch(written=written, candidates=by_email, best=by_email[0])
        folded = folded.replace(address, " ")
    # Text in parentheses or after a comma says who someone is, such as
    # their company, and must not keep the name from fitting.
    head = re.split(r"[(,/]", folded, maxsplit=1)[0]
    words = _words(head) or _words(folded)
    if not words:
        return PersonMatch(written=written)

    scored: list[tuple[int, PersonCandidate]] = []
    for candidate in candidates:
        alias_hit = len(words) == 1 and any(words[0] == _fold(a) for a in candidate.aliases)
        score = 100 if alias_hit else _score(words, candidate)
        if score > 0:
            scored.append((score, candidate))
    if not scored:
        return PersonMatch(written=written)
    scored.sort(key=lambda pair: (-pair[0], pair[1].kind.value, pair[1].name))
    top = scored[0][0]
    leaders = [c for s, c in scored if s == top]
    return PersonMatch(
        written=written,
        candidates=[c for _, c in scored[:_SUGGESTIONS_MAX]],
        best=leaders[0] if len(leaders) == 1 else None,
    )
