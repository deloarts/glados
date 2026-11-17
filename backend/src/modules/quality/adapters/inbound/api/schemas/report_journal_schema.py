"""
Wire schemas of the export journal.
"""

import json
from datetime import datetime
from typing import Literal
from uuid import UUID

from fastapi import HTTPException
from fastapi import status
from pydantic import BaseModel
from pydantic import Field
from pydantic import ValidationError

from src.modules.platform.adapters.inbound.api.schemas.base import EntityResponse
from src.modules.platform.domain.value_objects.language import Language
from src.modules.quality.application.dto.report_journal_dto import ReportExportFacts
from src.modules.quality.domain.value_objects.print_classifier import UploadedPrintDocument

SHA256_PATTERN = r"^[0-9a-fA-F]{64}$"
OPTION_KEY_PATTERN = r"^[a-zA-Z][a-zA-Z0-9_]{0,63}$"
MAX_OPTIONS = 20


class ReportExportFactsRequest(BaseModel):
    language: Language
    options: dict[str, bool] = Field(default_factory=dict, max_length=MAX_OPTIONS)
    report_version: str = Field(..., min_length=1, max_length=64)
    engine_version: int | None = Field(default=None, ge=1)

    def to_facts(self) -> ReportExportFacts:
        return ReportExportFacts(
            language=self.language.value,
            options=self.options,
            report_version=self.report_version,
            engine_version=self.engine_version,
        )


class ReportDownloadRequest(BaseModel):
    document: UploadedPrintDocument
    root_public_id: UUID
    facts: ReportExportFactsRequest
    byte_size: int = Field(..., ge=1)
    sha256: str = Field(..., pattern=SHA256_PATTERN)


class ReportJournalEntryResponse(EntityResponse):
    created: datetime
    actor_id: int
    actor_full_name: str
    action: Literal["download", "print", "mail"]
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
    # The addresses of a mailed report, To first and then Cc.
    recipients: list[str] | None = None


def export_facts(
    language: str | None,
    options: str | None,
    report_version: str | None,
    engine_version: int | None,
) -> ReportExportFacts | None:
    """The export facts sent along with a printed report as form fields, or
    None when the client sent none; a print without them is not journalled."""
    if language is None or report_version is None:
        return None
    try:
        parsed = json.loads(options) if options else {}
        return ReportExportFactsRequest.model_validate(
            {
                "language": language,
                "options": parsed,
                "report_version": report_version,
                "engine_version": engine_version,
            }
        ).to_facts()
    except (ValueError, ValidationError) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"The report facts are not valid: {exc}",
        ) from exc
