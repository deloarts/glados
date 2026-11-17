"""
The rules of distributing meeting notes: which cards a PDF includes, the
version check of the cards a PDF was built from, the issue labels, what
counts as a change since a send, and blanking anonymised people in
snapshots.
"""

from datetime import UTC
from datetime import datetime

import pytest

from src.modules.workspace.domain.entities.meeting import Meeting
from src.modules.workspace.domain.entities.meeting import MeetingAttendee
from src.modules.workspace.domain.entities.meeting import MeetingCard
from src.modules.workspace.domain.entities.meeting import MeetingDecision
from src.modules.workspace.domain.entities.meeting import MeetingTodo
from src.modules.workspace.domain.entities.meeting import MeetingTodoOwner
from src.modules.workspace.domain.entities.meeting_snapshot import MeetingSnapshot
from src.modules.workspace.domain.errors import MeetingInvalidInputError
from src.modules.workspace.domain.errors import MeetingNotesOutdatedError
from src.modules.workspace.domain.services.meeting_issue import IssueLabel
from src.modules.workspace.domain.services.meeting_issue import assert_cards_current
from src.modules.workspace.domain.services.meeting_issue import assert_label
from src.modules.workspace.domain.services.meeting_issue import changes_since
from src.modules.workspace.domain.services.meeting_issue import included_cards
from src.modules.workspace.domain.services.meeting_issue import print_label
from src.modules.workspace.domain.services.meeting_issue import send_label
from src.modules.workspace.domain.services.meeting_snapshot_anonymisation import blank_contact
from src.modules.workspace.domain.services.meeting_snapshot_anonymisation import blank_guest
from src.modules.workspace.domain.services.meeting_snapshot_builder import build_snapshot
from src.modules.workspace.domain.value_objects.meeting import MeetingAttendanceStatus
from src.modules.workspace.domain.value_objects.meeting import MeetingAttendeeKind
from src.modules.workspace.domain.value_objects.meeting import MeetingDistributionKind

AT = datetime(2026, 11, 6, 9, 0, tzinfo=UTC)
NO_INTERNAL = {"include_internal": False, "include_todos": True}


def _card(id: int, *, position: int = 0, body: str = "Text", internal: bool = False, version=0):
    return MeetingCard(
        id=id,
        meeting_id=1,
        position=position,
        scope=f"Scope {id}",
        scope_icon=None,
        body=body,
        internal=internal,
        created=AT,
        creator_id=1,
        edit_version=version,
    )


def _todo(id: int, card_id: int) -> MeetingTodo:
    return MeetingTodo(
        id=id, meeting_id=1, card_id=card_id, position=0, title="Do", created=AT, creator_id=1
    )


def _decision(id: int, card_id: int, text: str = "Decided") -> MeetingDecision:
    return MeetingDecision(
        id=id, meeting_id=1, card_id=card_id, position=0, text=text, created=AT, creator_id=1
    )


def _meeting() -> Meeting:
    return Meeting(
        id=1,
        meeting_number="MTG-26-0001",
        name="Review",
        starts_at=AT,
        ends_at=AT,
        created=AT,
        creator_id=1,
        project_id=7,
        owner_number="26-0142",
        attendees=[
            MeetingAttendee(
                id=11,
                kind=MeetingAttendeeKind.CONTACT,
                status=MeetingAttendanceStatus.PRESENT,
                contact_id=5,
                name="Thomas",
                email="T.B@example.com",
            ),
            MeetingAttendee(
                id=12,
                kind=MeetingAttendeeKind.GUEST,
                status=MeetingAttendanceStatus.DISTRIBUTION_ONLY,
                name="Paul",
                email="p@example.com",
            ),
        ],
    )


def _snapshot(cards, decisions, todos, options=NO_INTERNAL) -> MeetingSnapshot:
    return build_snapshot(
        _meeting(),
        kind=MeetingDistributionKind.SENT,
        actor_id=1,
        at=AT,
        cards=included_cards(cards, options),
        decisions=decisions,
        todos=todos,
        files=[],
        options=options,
        label=IssueLabel(1, draft=False),
        language="enGB",
        byte_size=10,
        sha256="a" * 64,
    )


class TestCards:
    def test_internal_cards_are_left_out_unless_asked_for(self):
        cards = [_card(2, position=1), _card(1, position=0, internal=True)]

        assert [c.id for c in included_cards(cards, NO_INTERNAL)] == [2]
        assert [c.id for c in included_cards(cards, {"include_internal": True})] == [1, 2]

    def test_the_versions_must_match_the_cards_the_pdf_includes(self):
        cards = [_card(1, version=3), _card(2, internal=True)]

        assert [c.id for c in assert_cards_current(cards, NO_INTERNAL, {1: 3})] == [1]
        with pytest.raises(MeetingNotesOutdatedError, match="changed"):
            assert_cards_current(cards, NO_INTERNAL, {1: 2})
        with pytest.raises(MeetingNotesOutdatedError, match="added"):
            assert_cards_current(cards, NO_INTERNAL, {})
        with pytest.raises(MeetingNotesOutdatedError, match="deleted"):
            assert_cards_current(cards, NO_INTERNAL, {1: 3, 9: 0})
        with pytest.raises(MeetingInvalidInputError):
            assert_cards_current(cards, NO_INTERNAL, {1: 3, 2: 0})


class TestLabels:
    def test_the_revisions_name_issue_draft_and_draft_after_issue(self):
        assert IssueLabel(2, draft=False).revision == "2"
        assert IssueLabel(2, draft=True).revision == "2-draft"
        assert IssueLabel(0, draft=True).revision == "draft"

    def test_a_send_carries_the_next_issue_and_a_print_the_last_unless_changed(self):
        nothing = changes_since(None, [], [], [])
        card = _card(1)
        changed = changes_since(_snapshot([card], [], []), [_card(1, body="New")], [], [])

        assert send_label(0) == IssueLabel(1, draft=False)
        assert print_label(0, nothing) == IssueLabel(0, draft=True)
        assert print_label(2, nothing) == IssueLabel(2, draft=False)
        assert print_label(2, changed) == IssueLabel(2, draft=True)

    def test_a_pdf_with_another_label_is_outdated(self):
        assert_label(IssueLabel(1, draft=False), 1, False)
        with pytest.raises(MeetingNotesOutdatedError):
            assert_label(IssueLabel(1, draft=True), 1, False)


class TestChangesSinceSend:
    def test_ticking_a_todo_off_is_no_change(self):
        card, todo = _card(1), _todo(5, 1)
        sent = _snapshot([card], [], [todo])
        todo.done_at = AT

        assert not changes_since(sent, [card], [], [todo]).any

    def test_text_decisions_todos_and_cards_count(self):
        card, other = _card(1), _card(2, position=1)
        sent = _snapshot([card, other], [_decision(3, 1)], [_todo(5, 1)])

        new_todo = changes_since(sent, [card, other], [_decision(3, 1)], [_todo(5, 1), _todo(6, 2)])
        new_decision = changes_since(
            sent, [card, other], [_decision(3, 1, "Changed")], [_todo(5, 1)]
        )
        removed = changes_since(sent, [card], [_decision(3, 1)], [_todo(5, 1)])
        added = changes_since(
            sent, [card, other, _card(4, position=2)], [_decision(3, 1)], [_todo(5, 1)]
        )
        internal_added = changes_since(
            sent,
            [card, other, _card(4, position=2, internal=True)],
            [_decision(3, 1)],
            [_todo(5, 1)],
        )

        assert new_todo.changed_card_ids == [2]
        assert new_decision.changed_card_ids == [1]
        assert removed.removed_card_ids == [2]
        assert added.added_card_ids == [4]
        assert not internal_added.any


class TestAnonymisation:
    def test_a_contact_is_blanked_with_its_addresses_and_the_checksum_stays(self):
        card = _card(1)
        todo = _todo(5, 1)
        todo.owners = [MeetingTodoOwner(id=0, contact_id=5, name="Thomas")]
        snapshot = _snapshot([card], [], [todo])
        snapshot.recipients = ["t.b@example.com", "p@example.com"]
        snapshot.cc = ["T.B@EXAMPLE.COM"]

        blank_contact(snapshot, 5, {"t.b@example.com"})

        assert (snapshot.attendees[0].name, snapshot.attendees[0].email) == ("", None)
        assert snapshot.attendees[0].anonymised is True
        assert snapshot.cards[0].todos[0].owners[0].name == ""
        assert snapshot.recipients == ["", "p@example.com"]
        assert snapshot.cc == [""]
        assert snapshot.sha256 == "a" * 64
        assert snapshot.attendees[1].name == "Paul"

    def test_a_guest_is_blanked_by_its_attendee_row(self):
        snapshot = _snapshot([_card(1)], [], [])
        snapshot.recipients = ["p@example.com"]

        blank_guest(snapshot, 12, {"p@example.com"})

        assert snapshot.attendees[1].name == "" and snapshot.attendees[1].anonymised
        assert snapshot.recipients == [""]
        assert snapshot.attendees[0].name == "Thomas"

    def test_the_snapshot_names_its_contacts(self):
        todo = _todo(5, 1)
        todo.owners = [MeetingTodoOwner(id=0, contact_id=8)]
        snapshot = _snapshot([_card(1)], [], [todo])
        snapshot.recipient_contact_ids = [9]

        assert snapshot.contact_ids() == {5, 8, 9}
