"""
DTOs for the Checklist aggregate.
"""

from pydantic import BaseModel
from pydantic import Field

from src.modules.quality.application.dto.controlled_document_dto import ControlledDocumentResult

# ══════════════════════════════════════════════════════════════════════
# Commands
# ══════════════════════════════════════════════════════════════════════


class CreateChecklistCommand(BaseModel):
    type: str
    title: str
    header: dict[str, str]
    answers: dict[str, str]
    remarks: dict[str, str]
    definition_version: int
    item_count: int
    project_id: int | None = None
    product_id: int | None = None


class UpdateChecklistCommand(BaseModel):
    title: str
    header: dict[str, str]
    answers: dict[str, str]
    remarks: dict[str, str]
    definition_version: int
    item_count: int
    project_id: int | None = None
    product_id: int | None = None


class ReviseChecklistCommand(BaseModel):
    reason: str


# ══════════════════════════════════════════════════════════════════════
# Results
# ══════════════════════════════════════════════════════════════════════


class ChecklistSummaryResult(ControlledDocumentResult):
    """List row: everything but the header, answers and remarks."""

    type: str
    title: str
    definition_version: int
    item_count: int
    answered_count: int
    finding_count: int
    verdict: str
    project_id: int | None
    project_number: str | None
    product_id: int | None
    product_number: str | None
    release_required: bool
    # Released, or for a type without a release, complete with a remark on
    # every finding (see ChecklistRules.is_finished).
    finished: bool
    # The machine the checklist is about, as its header saved it.
    designation: str | None


class ChecklistResult(ChecklistSummaryResult):
    header: dict[str, str]
    answers: dict[str, str]
    remarks: dict[str, str]
    changes: list[str] = Field(default_factory=list)
