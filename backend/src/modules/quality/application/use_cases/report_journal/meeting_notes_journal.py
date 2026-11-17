"""
Quality & documents' side of Workspace's meeting notes journal port: the
prints, downloads and sends of a meeting's notes are export journal entries
of the meeting notes report, with the meeting as their root and lineage and
the issue each PDF carried as their revision. A print goes to the printer
through the same path as every uploaded report.
"""

from uuid import UUID

from src.modules.platform.domain.entities.user import User
from src.modules.quality.application.dto.print_template_dto import PrintUploadedDocumentCommand
from src.modules.quality.application.dto.report_journal_dto import ReportExportFacts
from src.modules.quality.application.services import report_journal
from src.modules.quality.application.services.uploaded_document_roots import UploadedDocumentRoot
from src.modules.quality.application.use_cases.print_document.print_uploaded_document import (
    PrintUploadedDocument,
)
from src.modules.quality.domain.entities.report_journal_entry import ReportJournalEntry
from src.modules.quality.domain.value_objects.print_classifier import PrintRootType
from src.modules.quality.domain.value_objects.print_classifier import UploadedPrintDocument
from src.modules.quality.domain.value_objects.report_journal import ReportJournalAction
from src.modules.quality.ports.outbound.repositories.report_journal_repository import (
    IReportJournalRepository,
)
from src.modules.workspace.domain.value_objects.meeting import MeetingDistributionKind
from src.modules.workspace.ports.outbound.meeting_notes_journal_port import MeetingJournalEntry
from src.modules.workspace.ports.outbound.meeting_notes_journal_port import MeetingNotesExport
from src.modules.workspace.ports.outbound.meeting_notes_journal_port import MeetingPrintOutcome

_ACTIONS = {
    MeetingDistributionKind.PRINTED: ReportJournalAction.PRINT,
    MeetingDistributionKind.DOWNLOADED: ReportJournalAction.DOWNLOAD,
    MeetingDistributionKind.SENT: ReportJournalAction.MAIL,
}
_KINDS = {action: kind for kind, action in _ACTIONS.items()}


def _root(export: MeetingNotesExport) -> UploadedDocumentRoot:
    return UploadedDocumentRoot(
        root_type=PrintRootType.MEETING,
        root_id=export.meeting_id,
        lineage=export.meeting_public_id,
        revision=export.revision,
    )


def _facts(export: MeetingNotesExport) -> ReportExportFacts:
    return ReportExportFacts(
        language=export.language, options=dict(export.options), report_version=export.report_version
    )


def _to_entry(entry: ReportJournalEntry) -> MeetingJournalEntry:
    return MeetingJournalEntry(
        id=entry.id,
        public_id=entry.public_id,
        created=entry.created,
        actor_id=entry.actor_id,
        actor_full_name=entry.actor_full_name,
        kind=_KINDS[entry.action],
        revision=entry.revision,
        language=entry.language,
        options=dict(entry.options),
        report_version=entry.report_version,
        byte_size=entry.byte_size,
        sha256=entry.sha256,
        recipients=list(entry.recipients or []),
        copies=entry.copies,
        print_job_id=entry.print_job_id,
    )


class MeetingNotesJournal:
    """Implements Workspace's IMeetingNotesJournal."""

    def __init__(
        self, journal_repo: IReportJournalRepository, printing: PrintUploadedDocument
    ) -> None:
        self._journal = journal_repo
        self._printing = printing

    async def record(
        self,
        actor: User,
        kind: MeetingDistributionKind,
        export: MeetingNotesExport,
        *,
        recipients: list[str] | None = None,
    ) -> MeetingJournalEntry:
        entry = await report_journal.record(
            self._journal,
            actor,
            action=_ACTIONS[kind],
            document=UploadedPrintDocument.MEETING_NOTES,
            root=_root(export),
            facts=_facts(export),
            byte_size=export.byte_size,
            sha256=export.sha256,
            recipients=list(recipients) if recipients is not None else None,
        )
        return _to_entry(entry)

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
        cmd = PrintUploadedDocumentCommand(
            document=UploadedPrintDocument.MEETING_NOTES.value,
            root_public_id=export.meeting_public_id,
            printer_id=printer_id,
            copies=copies,
            two_sided=two_sided,
            data=data,
            facts=_facts(export),
        )
        job, entry = await self._printing.print_for_root(actor, cmd, _root(export), commit=False)
        return MeetingPrintOutcome(
            job_id=job.id,
            printer_id=job.printer_id,
            copies=job.copies,
            status=job.status,
            error_message=job.error_message,
            attributes_substituted=job.attributes_substituted,
            entry=_to_entry(entry) if entry is not None else None,
        )

    async def entries(self, meeting_public_id: UUID) -> list[MeetingJournalEntry]:
        rows = await self._journal.list_for_lineage(PrintRootType.MEETING.value, meeting_public_id)
        return [
            _to_entry(row) for row in rows if row.document == UploadedPrintDocument.MEETING_NOTES
        ]

    async def anonymise_recipients(self, entry_ids: list[int], addresses: set[str]) -> None:
        await self._journal.set_recipients_blank(entry_ids, {a.casefold() for a in addresses})
