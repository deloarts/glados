"""
Commands and results of the drafts of meeting notes: the draft an agent
submits, the reviewed form a person applies, and the drafts with the users
and contacts suggested for the names they carry.
"""

from datetime import date
from datetime import datetime
from datetime import time

from pydantic import BaseModel

from src.modules.platform.application.dto.base import ResultBase
from src.modules.platform.application.dto.base import ResultModel
from src.modules.workspace.application.dto.meeting_dto import MeetingAttendeeInput
from src.modules.workspace.application.dto.meeting_dto import MeetingResult
from src.modules.workspace.application.dto.meeting_dto import MeetingTodoOwnerInput
from src.modules.workspace.domain.services.person_name_matching import PersonKind
from src.modules.workspace.domain.value_objects.meeting import MeetingAttendanceStatus
from src.modules.workspace.domain.value_objects.meeting import MeetingScopeIcon

# ── Commands (inbound) ────────────────────────────────────────────────


class DraftAttendeeInput(BaseModel):
    name: str
    status: MeetingAttendanceStatus = MeetingAttendanceStatus.PRESENT
    email: str | None = None


class DraftTodoInput(BaseModel):
    title: str
    note: str | None = None
    due_date: date | None = None
    owners: list[str] = []


class DraftCardInput(BaseModel):
    scope: str | None = None
    scope_icon: MeetingScopeIcon | None = None
    body: str = ""
    internal: bool = False
    decisions: list[str] = []
    todos: list[DraftTodoInput] = []
    review_note: str | None = None


class DraftNewMeetingInput(BaseModel):
    name: str
    starts_at: datetime
    ends_at: datetime
    location: str | None = None
    tags: list[str] = []


class CreateMeetingNotesDraftCommand(BaseModel):
    """What an agent submits: the meeting it adds to, by id, or the owner and
    facts of a new one, and the notes."""

    meeting_id: int | None = None
    project_id: int | None = None
    product_id: int | None = None
    new_meeting: DraftNewMeetingInput | None = None
    attendees: list[DraftAttendeeInput] = []
    cards: list[DraftCardInput] = []
    next_meeting_date: date | None = None
    next_meeting_time: time | None = None
    next_meeting_location: str | None = None
    review_note: str | None = None
    token_name: str | None = None


class MeetingNotesDraftListQuery(BaseModel):
    meeting_id: int | None = None
    project_id: int | None = None
    product_id: int | None = None


class ApplyTodoInput(BaseModel):
    title: str
    note: str | None = None
    due_date: date | None = None
    owners: list[MeetingTodoOwnerInput] = []


class ApplyCardInput(BaseModel):
    scope: str | None = None
    scope_icon: MeetingScopeIcon | None = None
    body: str = ""
    internal: bool = False
    decisions: list[str] = []
    todos: list[ApplyTodoInput] = []


class ApplyNewMeetingInput(BaseModel):
    name: str
    starts_at: datetime
    ends_at: datetime
    location: str | None = None
    tags: list[str] = []


class ApplyMeetingNotesDraftCommand(BaseModel):
    """The reviewed form. For a draft of a new meeting it carries the
    meeting's facts; for one that adds to a meeting, the attendees it adds.
    The next meeting is set only on a new meeting or one that has none."""

    new_meeting: ApplyNewMeetingInput | None = None
    attendees: list[MeetingAttendeeInput] = []
    cards: list[ApplyCardInput] = []
    next_meeting_date: date | None = None
    next_meeting_time: time | None = None
    next_meeting_location: str | None = None


# ── Results (outbound) ────────────────────────────────────────────────


class PersonSuggestionResult(BaseModel):
    kind: PersonKind
    id: int
    name: str


class PersonMatchResult(BaseModel):
    """The users and contacts that may be meant by a name the notes carry,
    best first, and the one to preselect."""

    written: str
    candidates: list[PersonSuggestionResult]
    best: PersonSuggestionResult | None


class DraftAttendeeResult(BaseModel):
    name: str
    status: MeetingAttendanceStatus
    email: str | None


class DraftTodoResult(BaseModel):
    title: str
    note: str | None
    due_date: date | None
    owners: list[str]


class DraftCardResult(BaseModel):
    scope: str | None
    scope_icon: MeetingScopeIcon | None
    body: str
    internal: bool
    decisions: list[str]
    todos: list[DraftTodoResult]
    review_note: str | None


class DraftNewMeetingResult(BaseModel):
    name: str
    starts_at: datetime
    ends_at: datetime
    location: str | None
    tags: list[str]


class MeetingNotesDraftSummaryResult(ResultBase):
    created: datetime
    token_name: str | None
    meeting_id: int | None
    meeting_number: str | None
    meeting_name: str | None
    project_id: int | None
    product_id: int | None
    owner_number: str | None
    # The new meeting's name, or the name of the meeting it adds to.
    name: str | None
    starts_at: datetime | None
    card_count: int
    decision_count: int
    todo_count: int
    review_note: str | None


class MeetingNotesDraftResult(MeetingNotesDraftSummaryResult):
    new_meeting: DraftNewMeetingResult | None
    attendees: list[DraftAttendeeResult]
    cards: list[DraftCardResult]
    next_meeting_date: date | None
    next_meeting_time: time | None
    next_meeting_location: str | None
    # One entry per distinct name among the attendees and todo owners.
    people: list[PersonMatchResult]


class ApplyMeetingNotesDraftResult(ResultModel):
    meeting: MeetingResult
