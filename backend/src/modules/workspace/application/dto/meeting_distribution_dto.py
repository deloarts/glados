"""
Commands and results of the distribution of meeting notes: printing,
downloading and sending the PDF the browser built, the issue it carries,
the meeting's distribution list, the snapshots of what went out and the
suggested recipients of a send.

The cards, decisions and todos of a snapshot carry the fields of the
meeting's own cards under the same names, so the browser compares the
notes as they are with a snapshot field by field.
"""

from datetime import date
from datetime import datetime
from datetime import time
from uuid import UUID

from pydantic import BaseModel
from pydantic import ConfigDict

from src.modules.platform.application.dto.base import ResultBase
from src.modules.platform.application.dto.base import ResultModel
from src.modules.platform.application.dto.user_dto import PublicUserResult
from src.modules.workspace.application.dto.meeting_dto import MeetingTodoOwnerResult
from src.modules.workspace.domain.value_objects.meeting import MeetingAttendanceStatus
from src.modules.workspace.domain.value_objects.meeting import MeetingAttendeeKind
from src.modules.workspace.domain.value_objects.meeting import MeetingDistributionKind
from src.modules.workspace.domain.value_objects.meeting import MeetingFileCategory
from src.modules.workspace.domain.value_objects.meeting import MeetingOwnerKind
from src.modules.workspace.domain.value_objects.meeting import MeetingScopeIcon

# ── Commands (inbound) ────────────────────────────────────────────────


class MeetingNotesOptions(BaseModel):
    """The switches of the PDF. Internal cards are left out unless asked
    for."""

    model_config = ConfigDict(extra="forbid")

    include_todos: bool = True
    include_internal: bool = False
    list_documents: bool = True


class MeetingCardVersion(BaseModel):
    """A card the PDF contains, at the edit version it was built from."""

    id: int
    edit_version: int


class MeetingNotesBuild(BaseModel):
    """How the browser built the PDF and what it contains."""

    language: str
    report_version: str
    options: MeetingNotesOptions
    cards: list[MeetingCardVersion]
    # The issue printed on the PDF: issue `issue_number`, or with `draft` a
    # draft after it, or a plain draft when it is 0.
    issue_number: int
    draft: bool
    data: bytes
    file_name: str | None = None


class PrintMeetingNotesCommand(MeetingNotesBuild):
    printer_id: int
    copies: int = 1
    two_sided: bool = False


class DownloadMeetingNotesCommand(MeetingNotesBuild):
    pass


class SendMeetingNotesCommand(MeetingNotesBuild):
    # One address or several, separated by commas.
    to: str
    cc: str | None = None
    subject: str
    html_body: str
    # The meeting's documents sent along with the PDF, in this order.
    attach_file_ids: list[int] = []


# ── Results (outbound) ────────────────────────────────────────────────


class MeetingIssueLabelResult(ResultModel):
    """Issue `issue_number`, or with `draft` a draft after it ("Draft after
    issue 2"), or a plain draft when it is 0. `revision` is the same label
    as the export journal keeps it."""

    issue_number: int
    draft: bool
    revision: str


class MeetingIssueResult(ResultModel):
    """The issue the next PDFs carry: `send` for a send, `print` for a print
    or download now. The cards changed, added and removed since the last
    send name what makes a print a draft."""

    issue_number: int
    last_sent_at: datetime | None
    send: MeetingIssueLabelResult
    print: MeetingIssueLabelResult
    changed_card_ids: list[int]
    added_card_ids: list[int]
    removed_card_ids: list[int]


class MeetingDistributionEntryResult(ResultModel):
    """One print, download or send of the notes, from the export journal,
    with the snapshot of what it contained."""

    journal_entry_id: int
    journal_entry_public_id: UUID
    kind: MeetingDistributionKind
    at: datetime
    actor: PublicUserResult | None
    actor_full_name: str
    issue: MeetingIssueLabelResult
    language: str
    options: dict[str, bool]
    report_version: str
    byte_size: int
    sha256: str
    # To of a send; Cc separately. Both are empty for a print or download.
    recipients: list[str]
    cc: list[str]
    subject: str | None
    copies: int | None
    print_job_id: int | None
    snapshot_id: int | None


class MeetingPrintResult(ResultModel):
    """The print job, and the distribution entry of a print that reached
    the printer. A printer that failed answers a failed job without an
    entry."""

    job_id: int
    printer_id: int | None
    copies: int
    status: str
    error_message: str | None
    attributes_substituted: bool
    entry: MeetingDistributionEntryResult | None


class MeetingSnapshotTodoResult(ResultModel):
    id: int
    card_id: int
    position: int
    title: str
    note: str | None
    due_date: date | None
    done: bool
    done_at: datetime | None
    owners: list[MeetingTodoOwnerResult]


class MeetingSnapshotDecisionResult(ResultModel):
    id: int
    card_id: int
    position: int
    text: str
    created: datetime
    creator: PublicUserResult | None


class MeetingSnapshotCardResult(ResultModel):
    id: int
    position: int
    scope: str | None
    scope_icon: MeetingScopeIcon | None
    body: str
    internal: bool
    edit_version: int
    created: datetime
    creator: PublicUserResult | None
    changed: datetime | None
    changed_by: PublicUserResult | None
    decisions: list[MeetingSnapshotDecisionResult]
    todos: list[MeetingSnapshotTodoResult]


class MeetingSnapshotAttendeeResult(ResultModel):
    id: int
    kind: MeetingAttendeeKind
    status: MeetingAttendanceStatus
    position: int
    user: PublicUserResult | None
    contact_id: int | None
    # The user's name, or the copy kept for a contact or a guest.
    name: str
    email: str | None
    anonymised: bool


class MeetingSnapshotFileResult(ResultModel):
    id: int
    file_name: str
    size_bytes: int
    category: MeetingFileCategory


class MeetingSnapshotFactsResult(ResultModel):
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


class MeetingSnapshotResult(ResultBase):
    meeting_id: int
    journal_entry_id: int
    kind: MeetingDistributionKind
    created: datetime
    actor: PublicUserResult | None
    issue: MeetingIssueLabelResult
    language: str
    options: dict[str, bool]
    byte_size: int
    sha256: str
    meeting: MeetingSnapshotFactsResult
    cards: list[MeetingSnapshotCardResult]
    attendees: list[MeetingSnapshotAttendeeResult]
    files: list[MeetingSnapshotFileResult]
    attachments: list[MeetingSnapshotFileResult]
    recipients: list[str]
    cc: list[str]
    subject: str | None


class MeetingRecipientSourceResult(ResultModel):
    """Where a suggested address comes from: an attendee of the meeting, a
    contact of the project or product, a contact of the customer or the
    customer's own address."""

    kind: str  # attendee, project_contact, product_contact, customer_contact, customer
    attendee_id: int | None = None
    attendee_status: MeetingAttendanceStatus | None = None
    contact_id: int | None = None
    customer_id: int | None = None


class MeetingRecipientSuggestionResult(ResultModel):
    email: str
    name: str | None
    # Ticked when the dialog opens: attendees and the contacts that receive
    # meeting notes.
    preselected: bool
    sources: list[MeetingRecipientSourceResult]
