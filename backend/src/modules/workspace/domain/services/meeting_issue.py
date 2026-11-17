"""
Pure rules for the distribution of meeting notes: which cards a PDF
includes, that the cards a PDF was built from are still current, the issue
a PDF carries, and what changed since the notes were last sent. No I/O.

A meeting's issue counts its sends. The PDF of a send carries the next
issue. A print or download carries the last issue while nothing changed
since that send, otherwise it is a draft after that issue, and before the
first send it is a plain draft. The notes changed since a send when a card
it contained was removed or changed its text, scope, icon or internal flag,
got a new todo or changed its decisions, or when a card was added that the
send would have contained. Ticking a todo off is no change.
"""

from collections.abc import Mapping
from dataclasses import dataclass

from src.modules.workspace.domain.entities.meeting import MeetingCard
from src.modules.workspace.domain.entities.meeting import MeetingDecision
from src.modules.workspace.domain.entities.meeting import MeetingTodo
from src.modules.workspace.domain.entities.meeting_snapshot import MeetingSnapshot
from src.modules.workspace.domain.errors import MeetingInvalidInputError
from src.modules.workspace.domain.errors import MeetingNotesOutdatedError

# The options of a PDF of the notes, as the journal and the snapshot keep
# them. Left out, an option takes its default.
OPTION_INCLUDE_TODOS = "include_todos"
OPTION_INCLUDE_INTERNAL = "include_internal"
OPTION_LIST_DOCUMENTS = "list_documents"
OPTION_DEFAULTS: Mapping[str, bool] = {
    OPTION_INCLUDE_TODOS: True,
    OPTION_INCLUDE_INTERNAL: False,
    OPTION_LIST_DOCUMENTS: True,
}


@dataclass(frozen=True)
class IssueLabel:
    """Issue `issue_number`, or with `draft` a draft after that issue, or a
    plain draft when the issue number is 0."""

    issue_number: int
    draft: bool

    @property
    def revision(self) -> str:
        """The label as the export journal's revision keeps it: "2" for
        issue 2, "2-draft" for a draft after issue 2 and "draft" before the
        first send."""
        if not self.draft:
            return str(self.issue_number)
        return f"{self.issue_number}-draft" if self.issue_number else "draft"


@dataclass(frozen=True)
class ChangesSinceSend:
    changed_card_ids: list[int]
    added_card_ids: list[int]
    removed_card_ids: list[int]

    @property
    def any(self) -> bool:
        return bool(self.changed_card_ids or self.added_card_ids or self.removed_card_ids)


def option(options: Mapping[str, bool], key: str) -> bool:
    return options.get(key, OPTION_DEFAULTS[key])


def included_cards(cards: list[MeetingCard], options: Mapping[str, bool]) -> list[MeetingCard]:
    """The cards a PDF with the options contains, in their order: every
    card, the internal ones only when asked for."""
    with_internal = option(options, OPTION_INCLUDE_INTERNAL)
    ordered = sorted(cards, key=lambda c: (c.position, c.id))
    return [card for card in ordered if with_internal or not card.internal]


def _card_label(card: MeetingCard) -> str:
    return f"'{card.scope}' (#{card.id})" if card.scope else f"#{card.id}"


def assert_cards_current(
    cards: list[MeetingCard], options: Mapping[str, bool], versions: Mapping[int, int]
) -> list[MeetingCard]:
    """The cards the PDF contains, after checking that the browser built it
    from exactly these cards at these edit versions. A card changed, added
    or deleted since answers 409 naming it, so the browser builds the PDF
    again."""
    by_id = {card.id: card for card in cards}
    included = included_cards(cards, options)
    for card_id, version in versions.items():
        card = by_id.get(card_id)
        if card is None:
            raise MeetingNotesOutdatedError(
                f"Card #{card_id} was deleted since the notes were built; build them again."
            )
        if card.edit_version != version:
            raise MeetingNotesOutdatedError(
                f"Card {_card_label(card)} was changed since the notes were built; "
                "build them again."
            )
        if card.internal and not option(options, OPTION_INCLUDE_INTERNAL):
            raise MeetingInvalidInputError(
                f"Card {_card_label(card)} is internal, and the notes leave internal cards out."
            )
    for card in included:
        if card.id not in versions:
            raise MeetingNotesOutdatedError(
                f"Card {_card_label(card)} was added since the notes were built; build them again."
            )
    return included


def changes_since(
    snapshot: MeetingSnapshot | None,
    cards: list[MeetingCard],
    decisions: list[MeetingDecision],
    todos: list[MeetingTodo],
) -> ChangesSinceSend:
    """What changed since the snapshot of a send; nothing without one."""
    if snapshot is None:
        return ChangesSinceSend([], [], [])
    with_todos = option(snapshot.options, OPTION_INCLUDE_TODOS)
    with_internal = option(snapshot.options, OPTION_INCLUDE_INTERNAL)
    current = {card.id: card for card in cards}
    sent = {card.id: card for card in snapshot.cards}
    changed: list[int] = []
    removed: list[int] = []
    for sent_card in snapshot.cards:
        card = current.get(sent_card.id)
        if card is None:
            removed.append(sent_card.id)
            continue
        card_decisions = sorted(
            (d.position, d.id, d.text) for d in decisions if d.card_id == card.id
        )
        sent_decisions = sorted((d.position, d.id, d.text) for d in sent_card.decisions)
        sent_todo_ids = {t.id for t in sent_card.todos}
        new_todo = with_todos and any(
            t.card_id == card.id and t.id not in sent_todo_ids for t in todos
        )
        if (
            card.scope != sent_card.scope
            or card.scope_icon != sent_card.scope_icon
            or card.body != sent_card.body
            or card.internal != sent_card.internal
            or card_decisions != sent_decisions
            or new_todo
        ):
            changed.append(card.id)
    added = [
        card.id
        for card in sorted(cards, key=lambda c: (c.position, c.id))
        if card.id not in sent and (with_internal or not card.internal)
    ]
    return ChangesSinceSend(changed, added, removed)


def send_label(issue_number: int) -> IssueLabel:
    """The issue the PDF of the next send carries."""
    return IssueLabel(issue_number + 1, draft=False)


def print_label(issue_number: int, changes: ChangesSinceSend) -> IssueLabel:
    """The issue a print or download carries now."""
    if issue_number == 0:
        return IssueLabel(0, draft=True)
    return IssueLabel(issue_number, draft=changes.any)


def assert_label(expected: IssueLabel, issue_number: int, draft: bool) -> None:
    """Refuses a PDF built with another issue than it carries now, which
    happens when the notes were sent or changed meanwhile."""
    if expected.issue_number != issue_number or expected.draft != draft:
        raise MeetingNotesOutdatedError(
            "The issue of the notes changed since they were built; build them again."
        )
