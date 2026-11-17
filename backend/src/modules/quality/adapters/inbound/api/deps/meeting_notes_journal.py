"""Quality & documents' implementation of Workspace's meeting notes journal
port, which the composition root binds at startup."""

from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.platform.adapters.inbound.api.deps.database import get_unit_of_work
from src.modules.quality.adapters.inbound.api.deps.repositories import get_calculation_repo
from src.modules.quality.adapters.inbound.api.deps.repositories import get_checklist_repo
from src.modules.quality.adapters.inbound.api.deps.repositories import get_print_job_repo
from src.modules.quality.adapters.inbound.api.deps.repositories import get_printer_repo
from src.modules.quality.adapters.inbound.api.deps.repositories import get_report_journal_repo
from src.modules.quality.adapters.inbound.api.deps.services import get_printer_gateway
from src.modules.quality.application.services.uploaded_document_roots import UploadedDocumentRoots
from src.modules.quality.application.use_cases.print_document.print_uploaded_document import (
    PrintUploadedDocument,
)
from src.modules.quality.application.use_cases.report_journal.meeting_notes_journal import (
    MeetingNotesJournal,
)
from src.modules.workspace.api import IMeetingNotesJournal


def build_meeting_notes_journal(db: AsyncSession) -> IMeetingNotesJournal:
    """The export journal of meeting notes on one session."""
    journal_repo = get_report_journal_repo(db)
    printing = PrintUploadedDocument(
        printer_repo=get_printer_repo(db),
        job_repo=get_print_job_repo(db),
        roots=UploadedDocumentRoots(get_calculation_repo(db), get_checklist_repo(db)),
        gateway=get_printer_gateway(),
        uow=get_unit_of_work(db),
        journal_repo=journal_repo,
    )
    return MeetingNotesJournal(journal_repo, printing)
