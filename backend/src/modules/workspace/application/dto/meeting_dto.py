"""
Commands and results of the meeting use cases: meetings with their
attendees, cards, decisions, todos and files, the meeting lists, the open
points of a follow-up, the history, the card revisions, the scopes and the
tags.
"""

from datetime import date
from datetime import datetime
from datetime import time

from pydantic import BaseModel
from pydantic import Field

from src.modules.platform.application.dto.base import ResultBase
from src.modules.platform.application.dto.base import ResultModel
from src.modules.platform.application.dto.user_dto import PublicUserResult
from src.modules.workspace.domain.value_objects.meeting import MeetingAttendanceStatus
from src.modules.workspace.domain.value_objects.meeting import MeetingAttendeeKind
from src.modules.workspace.domain.value_objects.meeting import MeetingEventKind
from src.modules.workspace.domain.value_objects.meeting import MeetingFileCategory
from src.modules.workspace.domain.value_objects.meeting import MeetingOwnerKind
from src.modules.workspace.domain.value_objects.meeting import MeetingScopeIcon

# ── Commands (inbound) ────────────────────────────────────────────────


class MeetingAttendeeInput(BaseModel):
    """A user or a contact by id, or a guest by name. A guest that is on the
    meeting already carries its attendee id."""

    kind: MeetingAttendeeKind
    status: MeetingAttendanceStatus = MeetingAttendanceStatus.PRESENT
    user_id: int | None = None
    contact_id: int | None = None
    attendee_id: int | None = None
    name: str | None = None
    email: str | None = None


class MeetingFieldsCommand(BaseModel):
    name: str
    starts_at: datetime
    ends_at: datetime
    location: str | None = None
    next_meeting_date: date | None = None
    next_meeting_time: time | None = None
    next_meeting_location: str | None = None
    attendees: list[MeetingAttendeeInput] = []
    tags: list[str] = []


class CreateMeetingCommand(MeetingFieldsCommand):
    project_id: int | None = None
    product_id: int | None = None


class UpdateMeetingCommand(MeetingFieldsCommand):
    expected_edit_version: int


class MeetingListQuery(BaseModel):
    project_id: int | None = None
    product_id: int | None = None
    # For a product: its own meetings and those of each of its projects.
    include_projects: bool = True
    include_invalid: bool = True
    # Only the meetings that carry this tag, in any case.
    tag: str | None = None


class MeetingCardCommand(BaseModel):
    scope: str | None = None
    scope_icon: MeetingScopeIcon | None = None
    body: str = ""
    internal: bool = False
    expected_edit_version: int | None = None


class MeetingDecisionCommand(BaseModel):
    text: str
    position: int | None = None


class MeetingTodoOwnerInput(BaseModel):
    user_id: int | None = None
    contact_id: int | None = None


class MeetingTodoCommand(BaseModel):
    title: str
    note: str | None = None
    due_date: date | None = None
    owners: list[MeetingTodoOwnerInput] = []


class MeetingScopeQuery(BaseModel):
    project_id: int | None = None
    product_id: int | None = None
    query: str | None = None
    limit: int = 20


class MeetingTagQuery(BaseModel):
    query: str | None = None
    limit: int = 20


class RenameMeetingFileCommand(BaseModel):
    file_name: str = Field(..., min_length=1)


class RenameMeetingScopeCommand(BaseModel):
    project_id: int | None = None
    product_id: int | None = None
    from_scope: str
    to_scope: str


# ── Results (outbound) ────────────────────────────────────────────────


class MeetingOwnerResult(ResultModel):
    kind: MeetingOwnerKind
    id: int
    number: str
    # The product a project belongs to, None for a product or a project
    # without one.
    product_id: int | None


class MeetingRefResult(ResultModel):
    id: int
    meeting_number: str
    name: str


class MeetingAttendeeResult(ResultBase):
    kind: MeetingAttendeeKind
    status: MeetingAttendanceStatus
    position: int
    user: PublicUserResult | None
    contact_id: int | None
    # The user's name, or the copy kept for a contact or a guest.
    name: str
    email: str | None
    anonymised: bool


class MeetingTodoOwnerResult(ResultModel):
    user: PublicUserResult | None
    contact_id: int | None
    name: str


class MeetingTodoResult(ResultBase):
    meeting_id: int
    card_id: int
    position: int
    title: str
    note: str | None
    due_date: date | None
    done: bool
    done_at: datetime | None
    done_by: PublicUserResult | None
    created: datetime
    creator: PublicUserResult | None
    changed: datetime | None
    owners: list[MeetingTodoOwnerResult]


class MeetingDecisionResult(ResultBase):
    meeting_id: int
    card_id: int
    position: int
    text: str
    created: datetime
    creator: PublicUserResult | None


class MeetingCardResult(ResultBase):
    meeting_id: int
    position: int
    scope: str | None
    scope_icon: MeetingScopeIcon | None
    body: str
    internal: bool
    created: datetime
    creator: PublicUserResult | None
    changed: datetime | None
    changed_by: PublicUserResult | None
    edit_version: int
    decisions: list[MeetingDecisionResult]
    todos: list[MeetingTodoResult]


class MeetingFileResult(ResultBase):
    meeting_id: int
    card_id: int | None = None
    file_name: str
    stored_name: str
    mime_type: str
    size_bytes: int
    storage_path: str
    sha256: str
    category: MeetingFileCategory
    created: datetime
    uploaded_by_user_id: int
    url: str | None  # None when storage is disabled or url generation failed


class MeetingResult(ResultBase):
    meeting_number: str
    owner: MeetingOwnerResult
    name: str
    starts_at: datetime
    ends_at: datetime
    location: str | None
    next_meeting_date: date | None
    next_meeting_time: time | None
    next_meeting_location: str | None
    follow_up_of: MeetingRefResult | None
    valid: bool
    invalid_at: datetime | None
    invalid_by: PublicUserResult | None
    invalid_reason: str | None
    issue_number: int
    last_sent_at: datetime | None
    last_printed_at: datetime | None
    created: datetime
    creator: PublicUserResult | None
    changed: datetime | None
    changed_by: PublicUserResult | None
    edit_version: int
    attendees: list[MeetingAttendeeResult]
    tags: list[str]
    cards: list[MeetingCardResult]
    files: list[MeetingFileResult]


class MeetingScopeChipResult(ResultModel):
    scope: str | None
    icon: MeetingScopeIcon | None
    internal: bool


class MeetingAttendeeChipResult(ResultModel):
    kind: MeetingAttendeeKind
    status: MeetingAttendanceStatus
    user_id: int | None
    name: str


class MeetingListRowResult(ResultBase):
    meeting_number: str
    owner: MeetingOwnerResult
    name: str
    valid: bool
    starts_at: datetime
    ends_at: datetime
    location: str | None
    scopes: list[MeetingScopeChipResult]
    notes: str
    attendees: list[MeetingAttendeeChipResult]
    tags: list[str]
    open_todo_count: int
    overdue_todo_count: int
    sent: bool
    printed: bool


class MeetingOpenPointResult(ResultModel):
    """An open todo of a meeting the follow-up follows, with the meeting
    and card it belongs to."""

    todo: MeetingTodoResult
    meeting: MeetingRefResult
    meeting_starts_at: datetime
    card_scope: str | None


class MeetingEventResult(ResultBase):
    meeting_id: int
    kind: MeetingEventKind
    at: datetime
    actor: PublicUserResult | None
    card_id: int | None
    todo_id: int | None
    file_id: int | None
    summary: str | None
    details: dict[str, object] | None


class MeetingCardRevisionResult(ResultBase):
    card_id: int
    scope: str | None
    scope_icon: MeetingScopeIcon | None
    body: str
    internal: bool
    author: PublicUserResult | None
    created: datetime
    saved_at: datetime


class MeetingScopeSuggestionResult(ResultModel):
    scope: str
    icon: MeetingScopeIcon | None
    count: int


class MeetingScopeSuggestionsResult(ResultModel):
    suggestions: list[MeetingScopeSuggestionResult]
    # An existing scope the query nearly repeats, offered instead of it.
    near_duplicate: str | None


class MeetingTagSuggestionResult(ResultModel):
    name: str
    count: int


class MeetingTagSuggestionsResult(ResultModel):
    suggestions: list[MeetingTagSuggestionResult]


class RenameMeetingScopeResult(ResultModel):
    renamed: int
