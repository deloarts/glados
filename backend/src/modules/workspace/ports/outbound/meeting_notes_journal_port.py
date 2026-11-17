"""
The export journal of meeting notes, which Quality & documents keeps: every
print, download and send of a meeting's notes is an entry there, next to
the reports of calculations, checklists and lots, and the meeting keeps a
snapshot of what each one contained. Workspace owns this port and Quality &
documents implements it, so meeting code never reads the journal itself.

A meeting is the lineage of its entries, its public id the lineage id, and
the revision of an entry is the issue its PDF carried (see
`meeting_issue.py`).
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID

from src.modules.platform.domain.entities.user import User
from src.modules.workspace.domain.value_objects.meeting import MeetingDistributionKind


@dataclass(frozen=True)
class MeetingNotesExport:
    """One PDF of a meeting's notes as the journal records it."""

    meeting_id: int
    meeting_public_id: UUID
    revision: str
    language: str
    options: dict[str, bool]
    report_version: str
    byte_size: int
    sha256: str


@dataclass(frozen=True)
class MeetingJournalEntry:
    id: int
    public_id: UUID
    created: datetime
    actor_id: int
    actor_full_name: str
    kind: MeetingDistributionKind
    revision: str
    language: str
    options: dict[str, bool]
    report_version: str
    byte_size: int
    sha256: str
    # The addresses of a send, To first and then Cc; empty otherwise.
    recipients: list[str]
    copies: int | None
    print_job_id: int | None


@dataclass(frozen=True)
class MeetingPrintOutcome:
    """The print job, and the entry of a print that reached the printer."""

    job_id: int
    printer_id: int | None
    copies: int
    status: str
    error_message: str | None
    attributes_substituted: bool
    entry: MeetingJournalEntry | None


class IMeetingNotesJournal(Protocol):
    async def record(
        self,
        actor: User,
        kind: MeetingDistributionKind,
        export: MeetingNotesExport,
        *,
        recipients: list[str] | None = None,
    ) -> MeetingJournalEntry:
        """Journals a download or a send, without committing."""
        ...

    async def print(
        self,
        actor: User,
        export: MeetingNotesExport,
        data: bytes,
        *,
        printer_id: int,
        copies: int,
        two_sided: bool,
    ) -> MeetingPrintOutcome:
        """Sends the PDF to the printer and journals the print when it
        reached it. The read transaction is committed before the printer is
        reached; the job and the entry stay pending for the caller to commit
        with its snapshot. Raises when the actor may not print or the file
        is not a PDF; a printer that fails is a failed job."""
        ...

    async def entries(self, meeting_public_id: UUID) -> list[MeetingJournalEntry]:
        """Every entry of the meeting, newest first."""
        ...

    async def anonymise_recipients(self, entry_ids: list[int], addresses: set[str]) -> None:
        """Blanks the addresses, compared without case, among the recipients
        of the entries, without committing."""
        ...
