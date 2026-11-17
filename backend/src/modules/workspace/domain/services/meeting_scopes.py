"""
The scopes of meeting cards as one owner uses them: suggestions ranked by
how often each scope is used, and the existing scope a new one nearly
repeats, which differs only in case, spacing or a small typo. No I/O.
"""

from dataclasses import dataclass

from src.modules.workspace.domain.value_objects.meeting import MeetingScopeIcon


@dataclass(frozen=True)
class ScopeUse:
    """One scope as the cards of an owner use it: how many cards carry it
    and the icon most of them show."""

    scope: str
    count: int
    icon: MeetingScopeIcon | None


def scope_key(scope: str) -> str:
    """The scope with case and spacing taken out, for comparing."""
    return " ".join(scope.split()).casefold()


def _distance(a: str, b: str) -> int:
    """The edit distance between two strings, counting a swap of two
    neighbouring characters as one edit."""
    previous_previous: list[int] = []
    previous = list(range(len(b) + 1))
    for i in range(1, len(a) + 1):
        current = [i] + [0] * len(b)
        for j in range(1, len(b) + 1):
            cost = 0 if a[i - 1] == b[j - 1] else 1
            current[j] = min(previous[j] + 1, current[j - 1] + 1, previous[j - 1] + cost)
            if i > 1 and j > 1 and a[i - 1] == b[j - 2] and a[i - 2] == b[j - 1]:
                current[j] = min(current[j], previous_previous[j - 2] + 1)
        previous_previous, previous = previous, current
    return previous[len(b)]


def _allowed_typos(key: str) -> int:
    if len(key) < 4:
        return 0
    return 1 if len(key) < 10 else 2


def near_duplicate(entered: str, uses: list[ScopeUse]) -> str | None:
    """The existing scope the entered one nearly repeats, the most used one
    when several do, or None. An exact repeat is no near duplicate."""
    key = scope_key(entered)
    if not key:
        return None
    best: ScopeUse | None = None
    for use in uses:
        if use.scope == entered.strip():
            return None
        other = scope_key(use.scope)
        near = other == key or _distance(key, other) <= _allowed_typos(key)
        if near and (best is None or use.count > best.count):
            best = use
    return best.scope if best is not None else None


def ranked(uses: list[ScopeUse], query: str | None, limit: int) -> list[ScopeUse]:
    """The scopes that contain the query, most used first and then by name."""
    key = scope_key(query or "")
    matching = [use for use in uses if key in scope_key(use.scope)]
    return sorted(matching, key=lambda use: (-use.count, scope_key(use.scope)))[:limit]
