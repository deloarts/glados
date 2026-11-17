"""
HTTP schemas for the print-template settings surface, field sources, and
the manual print action.
"""

from datetime import datetime
from typing import Literal

from fastapi import Query
from pydantic import BaseModel
from pydantic import Field

from src.modules.platform.adapters.inbound.api.schemas.base import EntityResponse
from src.modules.platform.adapters.inbound.api.schemas.base import ResponseModel
from src.modules.platform.adapters.inbound.api.schemas.pagination_schema import PageParams
from src.modules.quality.domain.value_objects.print_classifier import PrintClassifier
from src.modules.quality.domain.value_objects.print_classifier import PrintJobStatus
from src.modules.quality.domain.value_objects.print_classifier import PrintJobTrigger
from src.modules.quality.domain.value_objects.print_classifier import PrintOutputKind
from src.modules.quality.domain.value_objects.print_classifier import PrintTrigger
from src.modules.quality.ports.outbound.repositories.print_job_repository import PrintJobFilterDto

# ══════════════════════════════════════════════════════════════════════
# PrintTemplate (settings)
# ══════════════════════════════════════════════════════════════════════


class PrintTemplateUpdateRequest(BaseModel):
    trigger: str | None = None
    source: str | None = None
    field_map: dict[str, str] | None = None
    printer_id: int | None = None
    auto_print: bool | None = None
    copies_rule: str | None = None
    copies_fixed: int | None = Field(default=None, ge=1)
    max_copies: int | None = Field(default=None, ge=1)
    design_dpi: int | None = None
    label_width_mm: float | None = None
    label_height_mm: float | None = None
    paper: str | None = None
    enabled: bool | None = None
    note: str | None = None


class PrintTemplateResponse(EntityResponse):
    created: datetime
    changed: datetime | None
    classifier: PrintClassifier
    output_kind: PrintOutputKind
    root_type: str
    trigger: PrintTrigger | None
    available_triggers: list[PrintTrigger] = Field(default_factory=list)
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


class FieldSourceResponse(ResponseModel):
    name: str
    kind: Literal["bare", "computed", "row"]
    description: str


class PreviewResponse(ResponseModel):
    rendered_zpl: str | None
    warnings: list[str] = Field(default_factory=list)


# ══════════════════════════════════════════════════════════════════════
# PrintJob (audit) + manual print
# ══════════════════════════════════════════════════════════════════════


class PrintJobResponse(EntityResponse):
    created: datetime
    template_id: int | None
    printer_id: int | None
    classifier: str
    root_type: str
    root_id: int
    copies: int
    status: PrintJobStatus
    error_message: str | None
    document_bytes: int | None
    trigger: PrintJobTrigger
    actor_id: int
    actor_full_name: str = ""


class UploadedPrintJobResponse(PrintJobResponse):
    # Set when the printer accepted the job without every requested setting,
    # such as two-sided output on a printer without a duplex unit.
    attributes_substituted: bool


class PrintJobFilterParams(PageParams):
    classifier: str | None = Query(default=None)
    root_type: str | None = Query(default=None)
    root_id: int | None = Query(default=None)
    printer_id: int | None = Query(default=None)
    status: Literal["printing", "sent", "failed"] | None = Query(default=None)

    def to_dto(self) -> PrintJobFilterDto:
        return PrintJobFilterDto(**self.model_dump())


class PrintRequestItemRequest(BaseModel):
    classifier: str
    printer_id: int | None = None
    copies: int | None = Field(default=None, ge=1)


class PrintRequestBody(BaseModel):
    root_type: str
    root_id: int
    items: list[PrintRequestItemRequest] = Field(..., min_length=1)
