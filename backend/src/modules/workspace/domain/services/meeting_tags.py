"""
The free-text tags of a meeting, such as "Milestone" or "Acceptance", that
let such meetings be found again: the rules a meeting's list of tags follows,
and the tags already in use ranked for suggestions. No I/O.
"""

from dataclasses import dataclass

from src.modules.workspace.domain.errors import MeetingInvalidInputError

TAG_MAX = 40
TAGS_MAX = 10


def tag_key(tag: str) -> str:
    """The tag with case and spacing taken out, for comparing."""
    return " ".join(tag.split()).casefold()


def normalise_tags(values: list[str]) -> list[str]:
    """The meeting's tags in the order given, each trimmed with its inner
    whitespace collapsed to single spaces. Empty tags are dropped and a tag
    that repeats an earlier one in another case is dropped too, so the first
    spelling stays. A tag longer than TAG_MAX characters and more than
    TAGS_MAX tags are refused."""
    tags: list[str] = []
    seen: set[str] = set()
    for value in values:
        tag = " ".join(value.split())
        if not tag:
            continue
        if len(tag) > TAG_MAX:
            raise MeetingInvalidInputError(f"A tag must be at most {TAG_MAX} characters.")
        key = tag.casefold()
        if key in seen:
            continue
        seen.add(key)
        tags.append(tag)
    if len(tags) > TAGS_MAX:
        raise MeetingInvalidInputError(f"A meeting carries at most {TAGS_MAX} tags.")
    return tags


@dataclass(frozen=True)
class TagUse:
    """One tag as the meetings use it: the spelling and how many meetings
    carry it."""

    name: str
    count: int


def ranked_tags(uses: list[TagUse], query: str | None, limit: int) -> list[TagUse]:
    """The tags in use that contain the query, spellings that differ only in
    case counted as one under the spelling most meetings use, most used
    first and then by name."""
    counts: dict[str, int] = {}
    spelling: dict[str, TagUse] = {}
    for use in uses:
        key = tag_key(use.name)
        counts[key] = counts.get(key, 0) + use.count
        best = spelling.get(key)
        if best is None or (use.count, best.name) > (best.count, use.name):
            spelling[key] = use
    wanted = tag_key(query or "")
    matching = [
        TagUse(name=spelling[key].name, count=count)
        for key, count in counts.items()
        if wanted in key
    ]
    return sorted(matching, key=lambda use: (-use.count, tag_key(use.name)))[:limit]
