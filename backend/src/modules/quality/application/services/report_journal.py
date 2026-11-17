"""
Writes export journal entries for the use cases a report leaves Glados
through, a download, a print or a mail, so all record the same facts.
"""

from src.modules.platform.domain.entities.user import User
from src.modules.quality.application.dto.report_journal_dto import ReportExportFacts
from src.modules.quality.application.dto.report_journal_dto import ReportJournalEntryResult
from src.modules.quality.application.services.uploaded_document_roots import UploadedDocumentRoot
from src.modules.quality.domain.entities.report_journal_entry import ReportJournalEntry
from src.modules.quality.domain.value_objects.print_classifier import UploadedPrintDocument
from src.modules.quality.domain.value_objects.report_journal import ReportJournalAction
from src.modules.quality.ports.outbound.repositories.report_journal_repository import (
    IReportJournalRepository,
)
from src.shared_kernel.domain.services.clock import now_utc


async def record(
    journal: IReportJournalRepository,
    actor: User,
    *,
    action: ReportJournalAction,
    document: UploadedPrintDocument,
    root: UploadedDocumentRoot,
    facts: ReportExportFacts,
    byte_size: int,
    sha256: str,
    print_job_id: int | None = None,
    copies: int | None = None,
    recipients: list[str] | None = None,
) -> ReportJournalEntry:
    return await journal.save(
        ReportJournalEntry(
            id=0,
            created=now_utc(),
            actor_id=actor.id,
            action=action,
            document=document,
            root_type=root.root_type,
            root_id=root.root_id,
            lineage=root.lineage,
            revision=root.revision,
            language=facts.language,
            options=dict(facts.options),
            report_version=facts.report_version,
            engine_version=facts.engine_version,
            byte_size=byte_size,
            sha256=sha256.lower(),
            print_job_id=print_job_id,
            copies=copies,
            recipients=recipients,
        )
    )


def to_result(entry: ReportJournalEntry) -> ReportJournalEntryResult:
    return ReportJournalEntryResult(
        id=entry.id,
        public_id=entry.public_id,
        created=entry.created,
        actor_id=entry.actor_id,
        actor_full_name=entry.actor_full_name,
        action=entry.action,
        document=entry.document,
        root_type=entry.root_type,
        root_id=entry.root_id,
        revision=entry.revision,
        language=entry.language,
        options=entry.options,
        report_version=entry.report_version,
        engine_version=entry.engine_version,
        byte_size=entry.byte_size,
        sha256=entry.sha256,
        print_job_id=entry.print_job_id,
        copies=entry.copies,
        recipients=entry.recipients,
    )
