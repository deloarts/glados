"""
The distribution of a document: every download and print of a report of
any of its revisions, newest first. Who may see the record may see where
its reports went.
"""

from uuid import UUID

from src.modules.platform.domain.entities.user import User
from src.modules.quality.application.dto.report_journal_dto import ReportJournalEntryResult
from src.modules.quality.application.services import report_journal
from src.modules.quality.application.services.uploaded_document_roots import UploadedDocumentRoots
from src.modules.quality.domain.value_objects.print_classifier import UploadedPrintDocument
from src.modules.quality.ports.outbound.repositories.report_journal_repository import (
    IReportJournalRepository,
)


class GetReportJournal:
    def __init__(
        self, journal_repo: IReportJournalRepository, roots: UploadedDocumentRoots
    ) -> None:
        self._journal = journal_repo
        self._roots = roots

    async def execute(
        self, actor: User, document: str, root_public_id: UUID
    ) -> list[ReportJournalEntryResult]:
        root = await self._roots.describe(actor, UploadedPrintDocument(document), root_public_id)
        entries = await self._journal.list_for_lineage(root.root_type.value, root.lineage)
        return [report_journal.to_result(entry) for entry in entries]
