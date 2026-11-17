"""
DTOs for the Sequence aggregate. The steps travel in their plain data form
(see sequence_content.steps_to_data); the wire schema checks their shape,
the domain rules their meaning.
"""

from typing import Any

from pydantic import BaseModel
from pydantic import Field

from src.modules.quality.application.dto.controlled_document_dto import ControlledDocumentResult

# ══════════════════════════════════════════════════════════════════════
# Commands
# ══════════════════════════════════════════════════════════════════════


class CreateSequenceCommand(BaseModel):
    product_id: int
    name: str
    steps: list[dict[str, Any]] = Field(default_factory=list)


class UpdateSequenceCommand(BaseModel):
    name: str
    steps: list[dict[str, Any]]


class ReviseSequenceCommand(BaseModel):
    reason: str


# ══════════════════════════════════════════════════════════════════════
# Results
# ══════════════════════════════════════════════════════════════════════


class SequenceSummaryResult(ControlledDocumentResult):
    product_id: int
    product_number: str | None
    name: str
    step_count: int


class SequenceResult(SequenceSummaryResult):
    steps: list[dict[str, Any]]
    # The names a released revision shows; None for a draft, which shows
    # the current ones.
    frozen: dict[str, Any] | None
    changes: list[str] = Field(default_factory=list)
