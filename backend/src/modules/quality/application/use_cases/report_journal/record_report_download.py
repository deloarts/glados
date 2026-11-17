"""
Records that a report of a saved record was downloaded. The browser built
the PDF and sends what it knows about it, its size and SHA-256 among them;
the record must be one the actor may see. Downloads of unsaved inputs have
no record and are not journalled.
"""

from src.modules.platform.domain.entities.user import User
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork
from src.modules.quality.application.dto.report_journal_dto import RecordReportDownloadCommand
from src.modules.quality.application.dto.report_journal_dto import ReportJournalEntryResult
from src.modules.quality.application.services import report_journal
from src.modules.quality.application.services.uploaded_document_roots import UploadedDocumentRoots
from src.modules.quality.domain.errors import PrintDocumentKindRefusedError
from src.modules.quality.domain.value_objects.print_classifier import UploadedPrintDocument
from src.modules.quality.domain.value_objects.report_journal import ReportJournalAction
from src.modules.quality.ports.outbound.repositories.report_journal_repository import (
    IReportJournalRepository,
)


class RecordReportDownload:
    def __init__(
        self,
        journal_repo: IReportJournalRepository,
        roots: UploadedDocumentRoots,
        *,
        uow: IUnitOfWork,
    ) -> None:
        self._journal = journal_repo
        self._roots = roots
        self._uow = uow

    async def execute(
        self, actor: User, cmd: RecordReportDownloadCommand
    ) -> ReportJournalEntryResult:
        document = UploadedPrintDocument(cmd.document)
        if document == UploadedPrintDocument.MEETING_NOTES:
            raise PrintDocumentKindRefusedError(
                "A download of meeting notes is recorded by its meeting, which keeps what "
                "they contained."
            )
        root = await self._roots.describe(actor, document, cmd.root_public_id)
        entry = await report_journal.record(
            self._journal,
            actor,
            action=ReportJournalAction.DOWNLOAD,
            document=document,
            root=root,
            facts=cmd.facts,
            byte_size=cmd.byte_size,
            sha256=cmd.sha256,
        )
        await self._uow.commit()
        log.info(
            "Report %r of %s #%s downloaded by user #%s.",
            document.value,
            root.root_type.value,
            root.root_id,
            actor.id,
        )
        return report_journal.to_result(entry)
