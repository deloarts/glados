"""
A meeting of a project or a product and the rows that belong to it: its
attendees, its cards with their revisions, decisions and todos, its files
and its history. Every signed-in user reads every meeting.

A meeting is not a controlled document. It has no release and no edit
lock; each card saves on its own with its edit version, and the notes stay
editable after they were printed or sent. A meeting marked invalid is read
only until a manager restores it.
"""

from dataclasses import dataclass
from dataclasses import field
from datetime import date
from datetime import datetime
from datetime import time

from src.modules.workspace.domain.value_objects.meeting import MeetingAttendanceStatus
from src.modules.workspace.domain.value_objects.meeting import MeetingAttendeeKind
from src.modules.workspace.domain.value_objects.meeting import MeetingEventKind
from src.modules.workspace.domain.value_objects.meeting import MeetingFileCategory
from src.modules.workspace.domain.value_objects.meeting import MeetingOwnerKind
from src.modules.workspace.domain.value_objects.meeting import MeetingScopeIcon
from src.shared_kernel.domain.entities.base import Entity


@dataclass
class MeetingAttendee(Entity):
    """One attendee: a user, a contact or a guest. A contact keeps a copy of
    its name and e-mail address as they were when it was added, so the
    meeting reads without access to contacts and an anonymised contact can
    be blanked here too."""

    kind: MeetingAttendeeKind
    status: MeetingAttendanceStatus
    position: int = 0
    meeting_id: int = 0
    user_id: int | None = None
    contact_id: int | None = None
    name: str | None = None
    email: str | None = None
    anonymised_at: datetime | None = None


@dataclass
class Meeting(Entity):
    meeting_number: str
    name: str
    starts_at: datetime
    ends_at: datetime
    created: datetime
    creator_id: int

    # Exactly one of the two owns the meeting.
    project_id: int | None = None
    product_id: int | None = None

    location: str | None = None

    # The next meeting as agreed, in the tenant's wall clock. A follow-up
    # takes it as its date, time and location.
    next_meeting_date: date | None = None
    next_meeting_time: time | None = None
    next_meeting_location: str | None = None

    follow_up_of_id: int | None = None

    invalid_at: datetime | None = None
    invalid_by_id: int | None = None
    invalid_reason: str | None = None

    # Counted up by every send of the notes, which also stamps last_sent_at;
    # a print or download stamps last_printed_at.
    issue_number: int = 0
    last_sent_at: datetime | None = None
    last_printed_at: datetime | None = None

    deleted: bool = False
    deleted_at: datetime | None = None

    changed: datetime | None = None
    changed_by_id: int | None = None
    edit_version: int = 0

    attendees: list[MeetingAttendee] = field(default_factory=list)

    # Free-text tags in their order, such as "Milestone", normalised by
    # `normalise_tags` so no two differ only in case.
    tags: list[str] = field(default_factory=list)

    # ── Denormalized (read-only, populated by the repository) ────────
    # The number of the owning project or product, and for a project the
    # product it belongs to.
    owner_number: str = ""
    owner_product_id: int | None = None

    @property
    def owner_kind(self) -> MeetingOwnerKind:
        return MeetingOwnerKind.PROJECT if self.project_id is not None else MeetingOwnerKind.PRODUCT

    @property
    def owner_id(self) -> int:
        owner = self.project_id if self.project_id is not None else self.product_id
        assert owner is not None  # a meeting always has exactly one owner
        return owner

    @property
    def invalid(self) -> bool:
        return self.invalid_at is not None


@dataclass
class MeetingCard(Entity):
    meeting_id: int
    position: int
    scope: str | None
    scope_icon: MeetingScopeIcon | None
    body: str
    internal: bool
    created: datetime
    creator_id: int
    changed: datetime | None = None
    changed_by_id: int | None = None
    edit_version: int = 0


@dataclass
class MeetingCardRevision(Entity):
    """One saved version of a card. Saves by the same author within ten
    minutes of the revision's start update it instead of adding one."""

    card_id: int
    scope: str | None
    scope_icon: MeetingScopeIcon | None
    body: str
    internal: bool
    author_id: int
    created: datetime
    saved_at: datetime


@dataclass
class MeetingCardMention(Entity):
    """A user a card mentions or once mentioned. The row stays when the
    mention is removed, so a user is notified once per card."""

    card_id: int
    user_id: int
    present: bool
    created: datetime


@dataclass
class MeetingDecision(Entity):
    meeting_id: int
    card_id: int
    position: int
    text: str
    created: datetime
    creator_id: int


@dataclass
class MeetingTodoOwner(Entity):
    """A user or a contact who owns a todo. A contact keeps a copy of its
    name, as an attendee does."""

    user_id: int | None = None
    contact_id: int | None = None
    name: str | None = None


@dataclass
class MeetingTodo(Entity):
    meeting_id: int
    card_id: int
    position: int
    title: str
    created: datetime
    creator_id: int
    note: str | None = None
    due_date: date | None = None
    done_at: datetime | None = None
    done_by_id: int | None = None
    changed: datetime | None = None
    changed_by_id: int | None = None
    owners: list[MeetingTodoOwner] = field(default_factory=list)

    @property
    def done(self) -> bool:
        return self.done_at is not None

    @property
    def owner_user_ids(self) -> set[int]:
        return {owner.user_id for owner in self.owners if owner.user_id is not None}


@dataclass
class MeetingEvent(Entity):
    """One line of a meeting's history. The card, todo and file ids are kept
    without a reference, since the history outlives what it names."""

    meeting_id: int
    kind: MeetingEventKind
    at: datetime
    actor_id: int | None
    card_id: int | None = None
    todo_id: int | None = None
    file_id: int | None = None
    # What the line names, such as the card's scope or the todo's title.
    summary: str | None = None
    # Further facts of the event, such as the invalid reason or, for a send,
    # the journal entry and recipients.
    details: dict[str, object] | None = None


@dataclass
class MeetingFile(Entity):
    """A file of a meeting on the shared attachment shape. A file pasted
    into a card names the card."""

    meeting_id: int
    file_name: str
    stored_name: str
    mime_type: str
    size_bytes: int
    storage_path: str
    sha256: str
    category: MeetingFileCategory
    created: datetime
    uploaded_by_user_id: int
    card_id: int | None = None


@dataclass
class PendingMeetingNotification(Entity):
    """The mentions and todo assignments of one meeting that wait for one
    recipient. The first of them starts the five minutes after which they go
    out together as one notification."""

    meeting_id: int
    recipient_id: int
    actor_ids: list[int]
    mention_count: int
    todo_count: int
    first_at: datetime
