"""
A snapshot of a meeting's notes as one print, download or send contained
them: the meeting's facts, the cards with their decisions and todos, the
attendees, the documents listed and attached, the options, the issue the PDF
carried, the recipients of a send and the size and SHA-256 of the file.

The cards, decisions and todos keep the ids and fields the meeting's own
cards have, so the notes as they are today compare with a snapshot field
by field. Users are kept by id; contacts and guests by id with a copy of
their name and e-mail address, which anonymising blanks while the checksum
stays as proof that the PDF went out.
"""

from dataclasses import dataclass
from dataclasses import field
from datetime import date
from datetime import datetime
from datetime import time

from src.modules.workspace.domain.value_objects.meeting import MeetingAttendanceStatus
from src.modules.workspace.domain.value_objects.meeting import MeetingAttendeeKind
from src.modules.workspace.domain.value_objects.meeting import MeetingDistributionKind
from src.modules.workspace.domain.value_objects.meeting import MeetingFileCategory
from src.modules.workspace.domain.value_objects.meeting import MeetingOwnerKind
from src.modules.workspace.domain.value_objects.meeting import MeetingScopeIcon
from src.shared_kernel.domain.entities.base import Entity


@dataclass
class SnapshotTodoOwner:
    user_id: int | None = None
    contact_id: int | None = None
    # The copy kept for a contact; a user's name is read when shown.
    name: str | None = None


@dataclass
class SnapshotTodo:
    id: int
    card_id: int
    position: int
    title: str
    note: str | None
    due_date: date | None
    done_at: datetime | None
    owners: list[SnapshotTodoOwner] = field(default_factory=list)


@dataclass
class SnapshotDecision:
    id: int
    card_id: int
    position: int
    text: str
    created: datetime
    creator_id: int


@dataclass
class SnapshotCard:
    id: int
    position: int
    scope: str | None
    scope_icon: MeetingScopeIcon | None
    body: str
    internal: bool
    edit_version: int
    created: datetime
    creator_id: int
    changed: datetime | None
    changed_by_id: int | None
    decisions: list[SnapshotDecision] = field(default_factory=list)
    # Empty when the todos were left out of the PDF.
    todos: list[SnapshotTodo] = field(default_factory=list)


@dataclass
class SnapshotAttendee:
    id: int
    kind: MeetingAttendeeKind
    status: MeetingAttendanceStatus
    position: int
    user_id: int | None = None
    contact_id: int | None = None
    # The copy kept for a contact or a guest; a user's name is read when
    # shown.
    name: str | None = None
    email: str | None = None
    anonymised: bool = False


@dataclass
class SnapshotFile:
    id: int
    file_name: str
    size_bytes: int
    category: MeetingFileCategory


@dataclass
class SnapshotFacts:
    meeting_number: str
    name: str
    starts_at: datetime
    ends_at: datetime
    location: str | None
    next_meeting_date: date | None
    next_meeting_time: time | None
    next_meeting_location: str | None
    owner_kind: MeetingOwnerKind
    owner_id: int
    owner_number: str


@dataclass
class MeetingSnapshot(Entity):
    meeting_id: int
    # The export journal entry of the print, download or send.
    journal_entry_id: int
    kind: MeetingDistributionKind
    created: datetime
    actor_id: int
    # The issue the PDF carried: issue `issue_number`, or with `issue_draft`
    # a draft after that issue, or a plain draft before the first send.
    issue_number: int
    issue_draft: bool
    language: str
    options: dict[str, bool]
    byte_size: int
    sha256: str
    facts: SnapshotFacts
    cards: list[SnapshotCard] = field(default_factory=list)
    attendees: list[SnapshotAttendee] = field(default_factory=list)
    # The documents the PDF listed, empty when they were left out.
    files: list[SnapshotFile] = field(default_factory=list)
    # The documents attached to a send besides the PDF.
    attachments: list[SnapshotFile] = field(default_factory=list)
    recipients: list[str] = field(default_factory=list)
    cc: list[str] = field(default_factory=list)
    subject: str | None = None
    # The contacts whose addresses are among the recipients, written once
    # with the snapshot so anonymising them finds it.
    recipient_contact_ids: list[int] = field(default_factory=list)

    def contact_ids(self) -> set[int]:
        """The contacts the snapshot keeps copies of."""
        ids = {a.contact_id for a in self.attendees if a.contact_id is not None}
        ids.update(self.recipient_contact_ids)
        for card in self.cards:
            for todo in card.todos:
                ids.update(o.contact_id for o in todo.owners if o.contact_id is not None)
        return ids
