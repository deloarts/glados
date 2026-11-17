"""
DTOs for the PrintTemplate settings surface and the manual print action.
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel
from pydantic import Field

from src.modules.platform.application.dto.base import ResultBase
from src.modules.quality.application.dto.report_journal_dto import ReportExportFacts

# ══════════════════════════════════════════════════════════════════════
# PrintTemplate (settings)
# ══════════════════════════════════════════════════════════════════════


class UpdatePrintTemplateCommand(BaseModel):
    trigger: str | None = None
    source: str | None = None
    field_map: dict[str, str] | None = None
    printer_id: int | None = None
    auto_print: bool | None = None
    copies_rule: str | None = None
    copies_fixed: int | None = None
    max_copies: int | None = None
    design_dpi: int | None = None
    label_width_mm: float | None = None
    label_height_mm: float | None = None
    paper: str | None = None
    enabled: bool | None = None
    note: str | None = None


class PrintTemplateResult(ResultBase):
    created: datetime
    changed: datetime | None
    classifier: str
    output_kind: str
    root_type: str
    trigger: str | None
    available_triggers: list[str] = Field(default_factory=list)
    copies_rules: list[str] = Field(default_factory=list)
    source: str | None
    field_map: dict[str, str] = Field(default_factory=dict)
    printer_id: int | None
    printer_name: str = ""
    auto_print: bool
    copies_rule: str
    copies_fixed: int
    max_copies: int
    design_dpi: int | None
    label_width_mm: float | None
    label_height_mm: float | None
    paper: str | None
    enabled: bool
    note: str | None
    creator_id: int | None
    creator_full_name: str = ""
    changed_by_id: int | None
    changed_by_full_name: str
    changes: list[str] = Field(default_factory=list)


class FieldSourceResult(BaseModel):
    name: str
    kind: str
    description: str


class PreviewPrintTemplateResult(BaseModel):
    rendered_zpl: str | None
    warnings: list[str] = Field(default_factory=list)


# ══════════════════════════════════════════════════════════════════════
# PrintJob (audit) + manual print
# ══════════════════════════════════════════════════════════════════════


class PrintJobResult(ResultBase):
    created: datetime
    template_id: int | None
    printer_id: int | None
    classifier: str
    root_type: str
    root_id: int
    copies: int
    status: str
    error_message: str | None
    document_bytes: int | None
    trigger: str
    actor_id: int
    actor_full_name: str = ""


class PrintUploadedDocumentCommand(BaseModel):
    """A finished PDF the browser rendered, to be sent to one printer as it
    is. `root_public_id` is the public id of the record the document
    belongs to, and the document kind decides what kind of record that is."""

    document: str  # UploadedPrintDocument
    root_public_id: UUID
    printer_id: int
    copies: int
    two_sided: bool
    data: bytes
    # How the browser built the report, for the export journal. A print
    # without it is not journalled.
    facts: ReportExportFacts | None = None


class UploadedPrintJobResult(PrintJobResult):
    """The job row, plus whether the printer said it did not apply every
    requested setting. Only the reply carries that; the job row does not."""

    attributes_substituted: bool
