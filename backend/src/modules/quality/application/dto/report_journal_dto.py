"""
DTOs of the export journal.
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from src.modules.platform.application.dto.base import ResultBase


class ReportExportFacts(BaseModel):
    """How the browser built a report: what the journal records besides the
    record, the actor and the file."""

    language: str
    options: dict[str, bool]
    report_version: str
    engine_version: int | None = None


class RecordReportDownloadCommand(BaseModel):
    document: str  # UploadedPrintDocument
    root_public_id: UUID
    facts: ReportExportFacts
    byte_size: int
    sha256: str


class ReportJournalEntryResult(ResultBase):
    created: datetime
    actor_id: int
    actor_full_name: str
    action: str
    document: str
    root_type: str
    root_id: int
    revision: str
    language: str
    options: dict[str, bool]
    report_version: str
    engine_version: int | None
    byte_size: int
    sha256: str
    print_job_id: int | None
    copies: int | None
    recipients: list[str] | None = None
