"""
DTOs for the Calculation aggregate.
"""

from typing import Any

from pydantic import BaseModel
from pydantic import Field

from src.modules.quality.application.dto.controlled_document_dto import ControlledDocumentResult

# ══════════════════════════════════════════════════════════════════════
# Commands
# ══════════════════════════════════════════════════════════════════════


class CreateCalculationCommand(BaseModel):
    tool: str
    title: str
    note: str | None = None
    inputs: dict[str, Any]
    results: dict[str, Any]
    input_version: int
    engine_version: int
    project_id: int | None = None
    product_id: int | None = None
    product_device_id: int | None = None


class ReviseCalculationCommand(BaseModel):
    reason: str


class UpdateCalculationCommand(BaseModel):
    title: str
    note: str | None = None
    inputs: dict[str, Any]
    results: dict[str, Any]
    input_version: int
    engine_version: int
    project_id: int | None = None
    product_id: int | None = None
    product_device_id: int | None = None


# ══════════════════════════════════════════════════════════════════════
# Results
# ══════════════════════════════════════════════════════════════════════


class CalculationSummaryResult(ControlledDocumentResult):
    """List row: everything but the inputs, which only the tool needs."""

    tool: str
    title: str
    note: str | None
    results: dict[str, Any]
    input_version: int
    engine_version: int
    project_id: int | None
    project_number: str | None
    product_id: int | None
    product_number: str | None
    product_device_id: int | None
    # Frozen at release, the device's current name before.
    product_device_name: str | None


class CalculationResult(CalculationSummaryResult):
    inputs: dict[str, Any]
    changes: list[str] = Field(default_factory=list)
