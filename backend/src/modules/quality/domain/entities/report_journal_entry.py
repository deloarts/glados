"""
One entry of the export journal: a PDF report of a saved record that left
Glados, as a download, a print or the attachment of a mail. It names who exported which revision
of which record, when, in which language and with which options, the
version of the report and of the calculation behind it, and the size and
SHA-256 of the file, so a copy that turns up later can be matched to its
entry byte for byte. Glados does not keep the file itself; the revision it
names never changes once released, so the report can be produced again.

Append only. The record it names may be deleted later; the entry stays.
"""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from src.modules.quality.domain.value_objects.print_classifier import PrintRootType
from src.modules.quality.domain.value_objects.print_classifier import UploadedPrintDocument
from src.modules.quality.domain.value_objects.report_journal import ReportJournalAction
from src.shared_kernel.domain.entities.base import Entity


@dataclass(kw_only=True)
class ReportJournalEntry(Entity):
    created: datetime
    actor_id: int  # → User
    action: ReportJournalAction
    document: UploadedPrintDocument  # the kind of report
    root_type: PrintRootType  # of the record
    root_id: int
    lineage: UUID
    revision: str
    language: str
    options: dict[str, bool]
    report_version: str
    # The version of the calculation engine the report recalculated with,
    # for calculation reports.
    engine_version: int | None
    byte_size: int
    sha256: str
    # The print job a print entry belongs to, and its number of copies.
    print_job_id: int | None = None
    copies: int | None = None
    # The addresses a mailed report went to, To first and then Cc.
    recipients: list[str] | None = None

    # ── Denormalized (read-only, populated by repository mapper) ──────
    actor_full_name: str = ""
