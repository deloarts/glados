"""
The words of a bundled meeting notification in one language, as the
backend's locale data files ship them (see
adapters/outbound/locale/meeting_activity.<language>.json). The rules in
meeting_rules.py put them together, so a language differs only in its data
file and never in code.

Every text is a str.format template. A sentence names `{names}`, `{times}`,
`{todos}` and `{meeting}`; the counted phrases name `{count}`; the title
names `{meeting}`.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class MeetingActivitySentences:
    """The three sentences of a notification, for one or for several actors,
    since a language may inflect the verb by the number of actors."""

    mentions_and_todos: str
    mentions: str
    todos: str


@dataclass(frozen=True)
class MeetingActivityPhrases:
    title: str
    # Stands in for the actors when none of them could be named.
    someone: str
    # Joins the names before the last one, and the last one to the rest.
    list_separator: str
    last_separator: str
    once: str
    twice: str
    times: str
    one_todo: str
    todos: str
    one_actor: MeetingActivitySentences
    several_actors: MeetingActivitySentences
