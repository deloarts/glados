"""
HTTP schemas for meetings: the meeting with its attendees, cards, decisions,
todos and files, the meeting lists, the open points, the history, card
revisions, scopes, tags and presence.
"""

from datetime import date
from datetime import datetime
from datetime import time

from pydantic import AwareDatetime
from pydantic import BaseModel
from pydantic import EmailStr
from pydantic import Field

from src.modules.platform.adapters.inbound.api.schemas.base import EntityResponse
from src.modules.platform.adapters.inbound.api.schemas.base import ResponseModel
from src.modules.platform.adapters.inbound.api.schemas.user_schema import PublicUserResponse
from src.modules.workspace.domain.value_objects.meeting import MeetingAttendanceStatus
from src.modules.workspace.domain.value_objects.meeting import MeetingAttendeeKind
from src.modules.workspace.domain.value_objects.meeting import MeetingEventKind
from src.modules.workspace.domain.value_objects.meeting import MeetingFileCategory
from src.modules.workspace.domain.value_objects.meeting import MeetingOwnerKind
from src.modules.workspace.domain.value_objects.meeting import MeetingScopeIcon

# ── Request schemas ───────────────────────────────────────────────────


class MeetingAttendeeRequest(BaseModel):
    """A user or a contact by id, or a guest by name and an optional e-mail
    address. A guest that is on the meeting already sends its attendee id."""

    kind: MeetingAttendeeKind
    status: MeetingAttendanceStatus = MeetingAttendanceStatus.PRESENT
    user_id: int | None = None
    contact_id: int | None = None
    attendee_id: int | None = None
    name: str | None = Field(default=None, max_length=200)
    email: EmailStr | None = None


class _MeetingFieldsRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    starts_at: AwareDatetime
    ends_at: AwareDatetime
    location: str | None = Field(default=None, max_length=200)
    # The next meeting as agreed, in the tenant's wall clock.
    next_meeting_date: date | None = None
    next_meeting_time: time | None = None
    next_meeting_location: str | None = Field(default=None, max_length=200)
    attendees: list[MeetingAttendeeRequest] = Field(default_factory=list, max_length=100)
    # Free text in the order given. The rules trim them, drop empty ones and
    # repeats in another case, and refuse more than 10 or one over 40
    # characters.
    tags: list[str] = Field(default_factory=list, max_length=100)


class MeetingCreateRequest(_MeetingFieldsRequest):
    # Exactly one of the two.
    project_id: int | None = None
    product_id: int | None = None


class MeetingUpdateRequest(_MeetingFieldsRequest):
    expected_edit_version: int


class MeetingInvalidateRequest(BaseModel):
    reason: str = Field(..., min_length=1, max_length=1000)


class MeetingRestoreRequest(BaseModel):
    note: str | None = Field(default=None, max_length=1000)


class MeetingCardCreateRequest(BaseModel):
    scope: str | None = Field(default=None, max_length=80)
    scope_icon: MeetingScopeIcon | None = None
    body: str = Field(default="", max_length=100_000)
    internal: bool = False


class MeetingCardUpdateRequest(MeetingCardCreateRequest):
    expected_edit_version: int


class MeetingCardOrderRequest(BaseModel):
    card_ids: list[int] = Field(..., max_length=1000)


class MeetingCardRevisionRestoreRequest(BaseModel):
    expected_edit_version: int


class MeetingCardPresenceRequest(BaseModel):
    # False when the user stops editing, so viewers drop them at once.
    editing: bool = True


class MeetingDecisionRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=2000)
    position: int | None = Field(default=None, ge=0)


class MeetingTodoOwnerRequest(BaseModel):
    # Exactly one of the two.
    user_id: int | None = None
    contact_id: int | None = None


class MeetingTodoRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=300)
    note: str | None = Field(default=None, max_length=4000)
    due_date: date | None = None
    owners: list[MeetingTodoOwnerRequest] = Field(default_factory=list, max_length=50)


class MeetingFileUpdateRequest(BaseModel):
    file_name: str = Field(..., min_length=1)


class MeetingScopeRenameRequest(BaseModel):
    # Exactly one of the two.
    project_id: int | None = None
    product_id: int | None = None
    from_scope: str = Field(..., min_length=1, max_length=80)
    to_scope: str = Field(..., min_length=1, max_length=80)


# ── Response schemas ──────────────────────────────────────────────────


class MeetingOwnerResponse(ResponseModel):
    kind: MeetingOwnerKind
    id: int
    number: str
    # The product a project belongs to; None for a product.
    product_id: int | None


class MeetingRefResponse(ResponseModel):
    id: int
    meeting_number: str
    name: str


class MeetingAttendeeResponse(EntityResponse):
    kind: MeetingAttendeeKind
    status: MeetingAttendanceStatus
    position: int
    user: PublicUserResponse | None
    contact_id: int | None
    # The user's current name, or the copy kept for a contact or a guest.
    name: str
    # Likewise the user's current address, or the copy kept for the others.
    email: str | None
    anonymised: bool


class MeetingTodoOwnerResponse(ResponseModel):
    user: PublicUserResponse | None
    contact_id: int | None
    name: str


class MeetingTodoResponse(EntityResponse):
    meeting_id: int
    card_id: int
    position: int
    title: str
    note: str | None
    due_date: date | None
    done: bool
    done_at: datetime | None
    done_by: PublicUserResponse | None
    created: datetime
    creator: PublicUserResponse | None
    changed: datetime | None
    owners: list[MeetingTodoOwnerResponse]


class MeetingDecisionResponse(EntityResponse):
    meeting_id: int
    card_id: int
    position: int
    text: str
    created: datetime
    creator: PublicUserResponse | None


class MeetingCardResponse(EntityResponse):
    meeting_id: int
    position: int
    scope: str | None
    scope_icon: MeetingScopeIcon | None
    # Markdown in the subset of meeting cards, in canonical form.
    body: str
    internal: bool
    created: datetime
    creator: PublicUserResponse | None
    changed: datetime | None
    changed_by: PublicUserResponse | None
    # Sent back as expected_edit_version by a save of the card.
    edit_version: int
    decisions: list[MeetingDecisionResponse]
    todos: list[MeetingTodoResponse]


class MeetingFileResponse(EntityResponse):
    meeting_id: int
    # The card an image was pasted into, if any.
    card_id: int | None
    file_name: str
    stored_name: str
    mime_type: str
    size_bytes: int
    storage_path: str
    sha256: str
    category: MeetingFileCategory
    created: datetime
    uploaded_by_user_id: int
    url: str | None


class MeetingResponse(EntityResponse):
    meeting_number: str
    owner: MeetingOwnerResponse
    name: str
    starts_at: datetime
    ends_at: datetime
    location: str | None
    next_meeting_date: date | None
    next_meeting_time: time | None
    next_meeting_location: str | None
    follow_up_of: MeetingRefResponse | None
    valid: bool
    invalid_at: datetime | None
    invalid_by: PublicUserResponse | None
    invalid_reason: str | None
    issue_number: int
    last_sent_at: datetime | None
    last_printed_at: datetime | None
    created: datetime
    creator: PublicUserResponse | None
    changed: datetime | None
    changed_by: PublicUserResponse | None
    # Sent back as expected_edit_version by an edit or a delete.
    edit_version: int
    attendees: list[MeetingAttendeeResponse]
    tags: list[str]
    cards: list[MeetingCardResponse]
    files: list[MeetingFileResponse]


class MeetingScopeChipResponse(ResponseModel):
    scope: str | None
    icon: MeetingScopeIcon | None
    internal: bool


class MeetingAttendeeChipResponse(ResponseModel):
    kind: MeetingAttendeeKind
    status: MeetingAttendanceStatus
    user_id: int | None
    name: str


class MeetingListRowResponse(EntityResponse):
    meeting_number: str
    owner: MeetingOwnerResponse
    name: str
    valid: bool
    starts_at: datetime
    ends_at: datetime
    location: str | None
    # The scopes of all cards in their order.
    scopes: list[MeetingScopeChipResponse]
    # The card texts as one short line without Markdown.
    notes: str
    attendees: list[MeetingAttendeeChipResponse]
    tags: list[str]
    open_todo_count: int
    overdue_todo_count: int
    sent: bool
    printed: bool


class MeetingOpenPointResponse(ResponseModel):
    todo: MeetingTodoResponse
    meeting: MeetingRefResponse
    meeting_starts_at: datetime
    card_scope: str | None


class MeetingEventResponse(EntityResponse):
    meeting_id: int
    kind: MeetingEventKind
    at: datetime
    actor: PublicUserResponse | None
    card_id: int | None
    todo_id: int | None
    file_id: int | None
    summary: str | None
    details: dict[str, object] | None


class MeetingCardRevisionResponse(EntityResponse):
    card_id: int
    scope: str | None
    scope_icon: MeetingScopeIcon | None
    body: str
    internal: bool
    author: PublicUserResponse | None
    created: datetime
    saved_at: datetime


class MeetingScopeSuggestionResponse(ResponseModel):
    scope: str
    icon: MeetingScopeIcon | None
    count: int


class MeetingScopeSuggestionsResponse(ResponseModel):
    suggestions: list[MeetingScopeSuggestionResponse]
    # An existing scope the query nearly repeats, offered instead of it.
    near_duplicate: str | None


class MeetingTagSuggestionResponse(ResponseModel):
    name: str
    # How many meetings carry the tag.
    count: int


class MeetingTagSuggestionsResponse(ResponseModel):
    suggestions: list[MeetingTagSuggestionResponse]


class MeetingScopeRenameResponse(ResponseModel):
    renamed: int
