"""
Sends a finished PDF the browser rendered, such as a calculation report, to
a printer the user picked. Nothing is rendered here and no print template
is involved: the document kind names the record the PDF belongs to, the
actor must be allowed to see that record, and the bytes go to the printer
unchanged.

A print that reached the printer is also written to the export journal,
with the SHA-256 of the bytes sent, when the browser said how it built the
report.

Like PrintDocument, a printer that is missing, out of use, unreachable or
rejects the job becomes a failed print_job row returned as a normal result.
What raises is what the actor got wrong: no print permission, a record they
cannot see, or a file that is not a PDF.
"""

import hashlib

from src.modules.platform.application.services.storage_asset import assert_within_size_limit
from src.modules.platform.domain.entities.user import User
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork
from src.modules.quality.application.dto.print_template_dto import PrintUploadedDocumentCommand
from src.modules.quality.application.dto.print_template_dto import UploadedPrintJobResult
from src.modules.quality.application.mappers.print_template_mapper import PrintJobMapper
from src.modules.quality.application.services import report_journal
from src.modules.quality.application.services.uploaded_document_roots import UploadedDocumentRoot
from src.modules.quality.application.services.uploaded_document_roots import UploadedDocumentRoots
from src.modules.quality.domain.entities.print_job import PrintJob
from src.modules.quality.domain.entities.report_journal_entry import ReportJournalEntry
from src.modules.quality.domain.errors import PrintDocumentInvalidTypeError
from src.modules.quality.domain.errors import PrintDocumentKindRefusedError
from src.modules.quality.domain.errors import PrintDocumentTooLargeError
from src.modules.quality.domain.errors import PrinterUnreachableError
from src.modules.quality.domain.errors import PrintRejectedError
from src.modules.quality.domain.services.printer_rules import PrinterRules
from src.modules.quality.domain.value_objects.print_classifier import PrintJobStatus
from src.modules.quality.domain.value_objects.print_classifier import PrintJobTrigger
from src.modules.quality.domain.value_objects.print_classifier import PrintSides
from src.modules.quality.domain.value_objects.print_classifier import UploadedPrintDocument
from src.modules.quality.domain.value_objects.report_journal import ReportJournalAction
from src.modules.quality.ports.outbound.printer_gateway_port import IPrinterGateway
from src.modules.quality.ports.outbound.repositories.print_job_repository import IPrintJobRepository
from src.modules.quality.ports.outbound.repositories.printer_repository import IPrinterRepository
from src.modules.quality.ports.outbound.repositories.report_journal_repository import (
    IReportJournalRepository,
)
from src.shared_kernel.domain.services.clock import now_utc

# A report with embedded fonts, charts and a company logo stays far below
# this; the limit only keeps an arbitrary upload off the printer.
MAX_BYTES = 25 * 1024 * 1024
MAX_COPIES = 10


class PrintUploadedDocument:
    def __init__(
        self,
        printer_repo: IPrinterRepository,
        job_repo: IPrintJobRepository,
        roots: UploadedDocumentRoots,
        *,
        gateway: IPrinterGateway,
        uow: IUnitOfWork,
        journal_repo: IReportJournalRepository | None = None,
    ) -> None:
        self._printers = printer_repo
        self._jobs = job_repo
        self._roots = roots
        self._journal = journal_repo
        self._gateway = gateway
        self._uow = uow

    async def execute(
        self, actor: User, cmd: PrintUploadedDocumentCommand
    ) -> UploadedPrintJobResult:
        PrinterRules.assert_can_print(actor)
        document = UploadedPrintDocument(cmd.document)
        if document == UploadedPrintDocument.MEETING_NOTES:
            raise PrintDocumentKindRefusedError(
                "Meeting notes are printed from their meeting, which keeps what they contained."
            )
        root = await self._roots.describe(actor, document, cmd.root_public_id)
        result, _ = await self.print_for_root(actor, cmd, root)
        return result

    async def print_for_root(
        self,
        actor: User,
        cmd: PrintUploadedDocumentCommand,
        root: UploadedDocumentRoot,
        *,
        commit: bool = True,
    ) -> tuple[UploadedPrintJobResult, ReportJournalEntry | None]:
        """Prints the document of a record the caller has described and
        checked already, and answers the job with the journal entry, which is
        None for a failed print or one without export facts. Without
        `commit` the job and the entry stay pending for the caller to commit
        with its own rows; the read transaction still ends before the
        printer is reached."""
        PrinterRules.assert_can_print(actor)
        document = UploadedPrintDocument(cmd.document)
        root_type, root_id = root.root_type, root.root_id
        assert_within_size_limit(
            cmd.data, MAX_BYTES, error=PrintDocumentTooLargeError, label="Print document"
        )
        if not cmd.data.startswith(b"%PDF-"):
            raise PrintDocumentInvalidTypeError("Print document is not a PDF.")

        copies = max(1, min(cmd.copies, MAX_COPIES))
        sides = PrintSides.TWO_SIDED_LONG_EDGE if cmd.two_sided else PrintSides.ONE_SIDED
        error_message: str | None = None
        substituted = False

        printer = await self._printers.get_by_id(cmd.printer_id)
        if printer is None:
            error_message = f"Printer #{cmd.printer_id} not found."
        else:
            error_message = PrinterRules.document_printer_problem(printer)
        if printer is not None and error_message is None:
            # Nothing is pending; ending the read transaction frees the
            # connection while the printer, which may be slow or offline,
            # answers. The job row is written in a second transaction.
            await self._uow.commit()
            try:
                delivery = await self._gateway.send(
                    printer, cmd.data, "application/pdf", copies, sides=sides
                )
                substituted = delivery.attributes_substituted
            except (PrinterUnreachableError, PrintRejectedError) as exc:
                error_message = str(exc)

        job = PrintJob(
            id=0,
            created=now_utc(),
            template_id=None,
            printer_id=printer.id if printer is not None else None,
            classifier=document,
            root_type=root_type,
            root_id=root_id,
            copies=copies,
            status=PrintJobStatus.FAILED if error_message else PrintJobStatus.SENT,
            error_message=error_message,
            rendered_zpl=None,
            document_bytes=len(cmd.data),
            trigger=PrintJobTrigger.MANUAL,
            source_event_id=None,
            actor_id=actor.id,
        )
        saved = await self._jobs.save(job)
        entry: ReportJournalEntry | None = None
        if self._journal is not None and cmd.facts is not None and not error_message:
            entry = await report_journal.record(
                self._journal,
                actor,
                action=ReportJournalAction.PRINT,
                document=document,
                root=root,
                facts=cmd.facts,
                byte_size=len(cmd.data),
                sha256=hashlib.sha256(cmd.data).hexdigest(),
                print_job_id=saved.id,
                copies=copies,
            )
        if commit:
            await self._uow.commit()

        if error_message:
            log.warning(f"Print of {document.value!r} failed: {error_message}")
        else:
            log.info(
                f"Printed {document.value!r} ({copies} copies, {sides.value}), job #{saved.id}."
            )
        result = UploadedPrintJobResult(
            **PrintJobMapper.to_result(saved).model_dump(),
            attributes_substituted=substituted,
        )
        return result, entry
