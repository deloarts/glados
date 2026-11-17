"""
The export journal of PDF reports: the browser records a download here
after building the PDF, and a record's distribution list reads it. Prints
are journalled by POST /print/document itself. Every route only requires
login; the use cases check that the actor may see the record.
"""

from uuid import UUID

from fastapi import APIRouter
from fastapi import Depends
from fastapi import Query
from fastapi import status

from src.modules.platform.adapters.inbound.api.auth_deps import get_current_active_user
from src.modules.platform.domain.entities.user import User
from src.modules.quality.adapters.inbound.api.deps.printing import (
    get_record_report_download_use_case,
)
from src.modules.quality.adapters.inbound.api.deps.printing import get_report_journal_use_case
from src.modules.quality.adapters.inbound.api.schemas.report_journal_schema import (
    ReportDownloadRequest,
)
from src.modules.quality.adapters.inbound.api.schemas.report_journal_schema import (
    ReportJournalEntryResponse,
)
from src.modules.quality.application.dto.report_journal_dto import RecordReportDownloadCommand
from src.modules.quality.application.dto.report_journal_dto import ReportJournalEntryResult
from src.modules.quality.application.use_cases.report_journal.get_report_journal import (
    GetReportJournal,
)
from src.modules.quality.application.use_cases.report_journal.record_report_download import (
    RecordReportDownload,
)
from src.modules.quality.domain.value_objects.print_classifier import UploadedPrintDocument

router = APIRouter()


@router.get("", response_model=list[ReportJournalEntryResponse])
async def read_report_journal(
    document: UploadedPrintDocument = Query(...),
    root_public_id: UUID = Query(...),
    actor: User = Depends(get_current_active_user),
    use_case: GetReportJournal = Depends(get_report_journal_use_case),
) -> list[ReportJournalEntryResult]:
    """Every download and print of a report of any revision of the record."""
    return await use_case.execute(actor, document.value, root_public_id)


@router.post(
    "/downloads",
    response_model=ReportJournalEntryResponse,
    status_code=status.HTTP_201_CREATED,
)
async def record_report_download(
    body: ReportDownloadRequest,
    actor: User = Depends(get_current_active_user),
    use_case: RecordReportDownload = Depends(get_record_report_download_use_case),
) -> ReportJournalEntryResult:
    return await use_case.execute(
        actor,
        RecordReportDownloadCommand(
            document=body.document.value,
            root_public_id=body.root_public_id,
            facts=body.facts.to_facts(),
            byte_size=body.byte_size,
            sha256=body.sha256,
        ),
    )
