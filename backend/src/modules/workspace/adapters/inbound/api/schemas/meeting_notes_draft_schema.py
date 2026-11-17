"""
HTTP schemas for the drafts of meeting notes AI agents prepare: the draft
with the users and contacts suggested for its names, and the reviewed form
a person applies.
"""

from datetime import date
from datetime import datetime
from datetime import time
from typing import Literal

from pydantic import AwareDatetime
from pydantic import BaseModel
from pydantic import Field

from src.modules.platform.adapters.inbound.api.schemas.base import EntityResponse
from src.modules.platform.adapters.inbound.api.schemas.base import ResponseModel
from src.modules.workspace.adapters.inbound.api.schemas.meeting_schema import MeetingAttendeeRequest
from src.modules.workspace.adapters.inbound.api.schemas.meeting_schema import MeetingResponse
from src.modules.workspace.adapters.inbound.api.schemas.meeting_schema import (
    MeetingTodoOwnerRequest,
)
from src.modules.workspace.domain.value_objects.meeting import MeetingAttendanceStatus
from src.modules.workspace.domain.value_objects.meeting import MeetingScopeIcon

# ── Request schemas ───────────────────────────────────────────────────


class MeetingNotesDraftTodoRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=300)
    note: str | None = Field(default=None, max_length=4000)
    due_date: date | None = None
    owners: list[MeetingTodoOwnerRequest] = Field(default_factory=list, max_length=10)


class MeetingNotesDraftCardRequest(BaseModel):
    scope: str | None = Field(default=None, max_length=80)
    scope_icon: MeetingScopeIcon | None = None
    body: str = Field(default="", max_length=100_000)
    internal: bool = False
    decisions: list[str] = Field(default_factory=list, max_length=50)
    todos: list[MeetingNotesDraftTodoRequest] = Field(default_factory=list, max_length=50)


class MeetingNotesDraftNewMeetingRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    starts_at: AwareDatetime
    ends_at: AwareDatetime
    location: str | None = Field(default=None, max_length=200)
    tags: list[str] = Field(default_factory=list, max_length=100)


class MeetingNotesDraftApplyRequest(BaseModel):
    """The reviewed draft. A draft of a new meeting sends the meeting's
    facts; one that adds to a meeting leaves them out. The attendees are
    those to add, and the next meeting is set only on a new meeting or one
    that has none."""

    new_meeting: MeetingNotesDraftNewMeetingRequest | None = None
    attendees: list[MeetingAttendeeRequest] = Field(default_factory=list, max_length=100)
    cards: list[MeetingNotesDraftCardRequest] = Field(..., min_length=1, max_length=100)
    next_meeting_date: date | None = None
    next_meeting_time: time | None = None
    next_meeting_location: str | None = Field(default=None, max_length=200)


# ── Response schemas ──────────────────────────────────────────────────


class PersonSuggestionResponse(ResponseModel):
    kind: Literal["user", "contact"]
    id: int
    name: str


class PersonMatchResponse(ResponseModel):
    written: str
    candidates: list[PersonSuggestionResponse]
    best: PersonSuggestionResponse | None


class MeetingNotesDraftAttendeeResponse(ResponseModel):
    name: str
    status: MeetingAttendanceStatus
    email: str | None


class MeetingNotesDraftTodoResponse(ResponseModel):
    title: str
    note: str | None
    due_date: date | None
    owners: list[str]


class MeetingNotesDraftCardResponse(ResponseModel):
    scope: str | None
    scope_icon: MeetingScopeIcon | None
    body: str
    internal: bool
    decisions: list[str]
    todos: list[MeetingNotesDraftTodoResponse]
    review_note: str | None


class MeetingNotesDraftNewMeetingResponse(ResponseModel):
    name: str
    starts_at: datetime
    ends_at: datetime
    location: str | None
    tags: list[str]


class MeetingNotesDraftSummaryResponse(EntityResponse):
    created: datetime
    token_name: str | None
    meeting_id: int | None
    meeting_number: str | None
    meeting_name: str | None
    project_id: int | None
    product_id: int | None
    owner_number: str | None
    name: str | None
    starts_at: datetime | None
    card_count: int
    decision_count: int
    todo_count: int
    review_note: str | None


class MeetingNotesDraftResponse(MeetingNotesDraftSummaryResponse):
    new_meeting: MeetingNotesDraftNewMeetingResponse | None
    attendees: list[MeetingNotesDraftAttendeeResponse]
    cards: list[MeetingNotesDraftCardResponse]
    next_meeting_date: date | None
    next_meeting_time: time | None
    next_meeting_location: str | None
    people: list[PersonMatchResponse]


class MeetingNotesDraftApplyResponse(ResponseModel):
    meeting: MeetingResponse
