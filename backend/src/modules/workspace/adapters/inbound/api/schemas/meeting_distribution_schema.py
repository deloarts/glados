"""
HTTP schemas for the distribution of meeting notes: the form fields a
print, download or send carries besides the PDF, the issue the next PDFs
carry, the distribution list, the snapshots and the suggested recipients.
"""

import json
from datetime import date
from datetime import datetime
from datetime import time
from typing import Literal
from uuid import UUID

from fastapi import HTTPException
from fastapi import status
from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field
from pydantic import TypeAdapter
from pydantic import ValidationError

from src.modules.platform.adapters.inbound.api.schemas.base import EntityResponse
from src.modules.platform.adapters.inbound.api.schemas.base import ResponseModel
from src.modules.platform.adapters.inbound.api.schemas.user_schema import PublicUserResponse
from src.modules.workspace.adapters.inbound.api.schemas.meeting_schema import (
    MeetingTodoOwnerResponse,
)
from src.modules.workspace.domain.value_objects.meeting import MeetingAttendanceStatus
from src.modules.workspace.domain.value_objects.meeting import MeetingAttendeeKind
from src.modules.workspace.domain.value_objects.meeting import MeetingDistributionKind
from src.modules.workspace.domain.value_objects.meeting import MeetingFileCategory
from src.modules.workspace.domain.value_objects.meeting import MeetingOwnerKind
from src.modules.workspace.domain.value_objects.meeting import MeetingScopeIcon

# ── Form fields ───────────────────────────────────────────────────────


class MeetingNotesOptionsRequest(BaseModel):
    """The switches the PDF was built with, sent as the JSON form field
    `options`. Internal cards are left out unless asked for."""

    model_config = ConfigDict(extra="forbid")

    include_todos: bool = True
    include_internal: bool = False
    list_documents: bool = True


class MeetingCardVersionRequest(BaseModel):
    """One card of the PDF at the edit version it was built from, sent in
    the JSON array form field `cards`."""

    id: int
    edit_version: int = Field(..., ge=0)


_CARDS = TypeAdapter(list[MeetingCardVersionRequest])
MAX_CARDS = 500


def unprocessable(what: str, exc: Exception) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        detail=f"The {what} are not valid: {exc}",
    )


def parse_options(value: str | None) -> MeetingNotesOptionsRequest:
    try:
        return MeetingNotesOptionsRequest.model_validate(json.loads(value) if value else {})
    except (ValueError, ValidationError) as exc:
        raise unprocessable("options", exc) from exc


def parse_cards(value: str) -> list[MeetingCardVersionRequest]:
    try:
        cards = _CARDS.validate_python(json.loads(value))
    except (ValueError, ValidationError) as exc:
        raise unprocessable("cards", exc) from exc
    if len(cards) > MAX_CARDS:
        raise unprocessable("cards", ValueError(f"at most {MAX_CARDS} cards"))
    if len({card.id for card in cards}) != len(cards):
        raise unprocessable("cards", ValueError("a card is listed twice"))
    return cards


# ── Response schemas ──────────────────────────────────────────────────


class MeetingIssueLabelResponse(ResponseModel):
    """Issue `issue_number` ("Issue 2"), or with `draft` a draft after it
    ("Draft after issue 2"), or a plain draft when it is 0 ("Draft").
    `revision` is the label as the export journal keeps it: "2", "2-draft"
    or "draft"."""

    issue_number: int
    draft: bool
    revision: str


class MeetingIssueResponse(ResponseModel):
    """The issue a send carries (`send`) and the one a print or download
    carries now (`print`). The cards changed, added and removed since the
    last send are what make a print a draft, and what the notes tag as
    changed after sending."""

    issue_number: int
    last_sent_at: datetime | None
    send: MeetingIssueLabelResponse
    print: MeetingIssueLabelResponse
    changed_card_ids: list[int]
    added_card_ids: list[int]
    removed_card_ids: list[int]


class MeetingDistributionEntryResponse(ResponseModel):
    """One print, download or send of the notes from the export journal.
    `snapshot_id` names the snapshot of what it contained."""

    journal_entry_id: int
    journal_entry_public_id: UUID
    kind: MeetingDistributionKind
    at: datetime
    actor: PublicUserResponse | None
    actor_full_name: str
    issue: MeetingIssueLabelResponse
    language: str
    options: dict[str, bool]
    report_version: str
    byte_size: int
    sha256: str
    recipients: list[str]
    cc: list[str]
    subject: str | None
    copies: int | None
    print_job_id: int | None
    snapshot_id: int | None


class MeetingPrintResponse(ResponseModel):
    """The print job, and the distribution entry of a print that reached
    the printer. A failed print answers `status` failed with its error and
    no entry."""

    job_id: int
    printer_id: int | None
    copies: int
    status: str
    error_message: str | None
    attributes_substituted: bool
    entry: MeetingDistributionEntryResponse | None


class MeetingSnapshotTodoResponse(ResponseModel):
    id: int
    card_id: int
    position: int
    title: str
    note: str | None
    due_date: date | None
    done: bool
    done_at: datetime | None
    owners: list[MeetingTodoOwnerResponse]


class MeetingSnapshotDecisionResponse(ResponseModel):
    id: int
    card_id: int
    position: int
    text: str
    created: datetime
    creator: PublicUserResponse | None


class MeetingSnapshotCardResponse(ResponseModel):
    """A card as the PDF contained it, with the fields of the meeting's own
    cards under the same names."""

    id: int
    position: int
    scope: str | None
    scope_icon: MeetingScopeIcon | None
    body: str
    internal: bool
    edit_version: int
    created: datetime
    creator: PublicUserResponse | None
    changed: datetime | None
    changed_by: PublicUserResponse | None
    decisions: list[MeetingSnapshotDecisionResponse]
    # Empty when the PDF left the todos out.
    todos: list[MeetingSnapshotTodoResponse]


class MeetingSnapshotAttendeeResponse(ResponseModel):
    id: int
    kind: MeetingAttendeeKind
    status: MeetingAttendanceStatus
    position: int
    user: PublicUserResponse | None
    contact_id: int | None
    name: str
    email: str | None
    anonymised: bool


class MeetingSnapshotFileResponse(ResponseModel):
    id: int
    file_name: str
    size_bytes: int
    category: MeetingFileCategory


class MeetingSnapshotFactsResponse(ResponseModel):
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


class MeetingSnapshotResponse(EntityResponse):
    """What one print, download or send contained. Anonymised contacts and
    guests read with blank names and addresses; the checksum stays."""

    meeting_id: int
    journal_entry_id: int
    kind: MeetingDistributionKind
    created: datetime
    actor: PublicUserResponse | None
    issue: MeetingIssueLabelResponse
    language: str
    options: dict[str, bool]
    byte_size: int
    sha256: str
    meeting: MeetingSnapshotFactsResponse
    cards: list[MeetingSnapshotCardResponse]
    attendees: list[MeetingSnapshotAttendeeResponse]
    # The documents the PDF listed, and those attached to a send.
    files: list[MeetingSnapshotFileResponse]
    attachments: list[MeetingSnapshotFileResponse]
    recipients: list[str]
    cc: list[str]
    subject: str | None


class MeetingRecipientSourceResponse(ResponseModel):
    kind: Literal["attendee", "project_contact", "product_contact", "customer_contact", "customer"]
    attendee_id: int | None
    attendee_status: MeetingAttendanceStatus | None
    contact_id: int | None
    customer_id: int | None


class MeetingRecipientSuggestionResponse(ResponseModel):
    """One address the send dialog offers, with every place it comes from.
    Pre-selected are the attendees and the contacts that receive meeting
    notes."""

    email: str
    name: str | None
    preselected: bool
    sources: list[MeetingRecipientSourceResponse]
