"""
A draft of meeting notes that an AI agent prepared from a record of the
meeting the user gave it, such as handwritten notes or a notebook page. It
waits for the person whose token created it: they review it in the web
app, match the names it carries to users, contacts or guests, and apply it,
which adds its cards with their decisions and todos to a meeting. Until
then nobody else sees it, nobody is notified and no meeting changes.

A draft targets an existing meeting or proposes a new one of a project or
a product. People are kept only as the text the agent read, since matching
them to users and contacts is the reviewer's decision. The agent may leave
a note for the reviewer on the draft and on each card, such as a passage it
could not read, which the review shows and the apply never writes.
"""

from dataclasses import dataclass
from dataclasses import field
from datetime import date
from datetime import datetime
from datetime import time

from src.modules.workspace.domain.value_objects.meeting import MeetingAttendanceStatus
from src.modules.workspace.domain.value_objects.meeting import MeetingScopeIcon
from src.shared_kernel.domain.entities.base import Entity


@dataclass
class DraftAttendee:
    """A person as the notes name them, with an e-mail address when the
    notes carry one."""

    name: str
    status: MeetingAttendanceStatus = MeetingAttendanceStatus.PRESENT
    email: str | None = None


@dataclass
class DraftTodo:
    title: str
    note: str | None = None
    due_date: date | None = None
    # The owners as the notes name them.
    owners: list[str] = field(default_factory=list)


@dataclass
class DraftCard:
    scope: str | None
    scope_icon: MeetingScopeIcon | None
    body: str
    internal: bool = False
    decisions: list[str] = field(default_factory=list)
    todos: list[DraftTodo] = field(default_factory=list)
    review_note: str | None = None


@dataclass
class DraftNewMeeting:
    """The meeting a draft proposes when it targets no existing one."""

    name: str
    starts_at: datetime
    ends_at: datetime
    location: str | None = None
    tags: list[str] = field(default_factory=list)


@dataclass
class DraftNextMeeting:
    day: date
    start_time: time | None = None
    location: str | None = None


@dataclass
class MeetingNotesDraft(Entity):
    creator_id: int
    created: datetime
    # Exactly one target: an existing meeting, or a new meeting of a
    # project or a product.
    meeting_id: int | None
    project_id: int | None
    product_id: int | None
    new_meeting: DraftNewMeeting | None
    attendees: list[DraftAttendee] = field(default_factory=list)
    cards: list[DraftCard] = field(default_factory=list)
    next_meeting: DraftNextMeeting | None = None
    review_note: str | None = None
    # The name of the agent token that created the draft, as it was then.
    token_name: str | None = None

    # ── Denormalized (read-only, populated by repository mapper) ──────
    meeting_number: str | None = None
    meeting_name: str | None = None
    owner_number: str | None = None
