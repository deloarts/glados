"""
DTOs for the MachinePool catalogue aggregate.
"""

from datetime import datetime

from pydantic import BaseModel
from pydantic import Field

from src.modules.fulfillment.application.dto.production_machine_dto import ProductionMachineResult
from src.modules.platform.application.dto.base import ResultBase

# ══════════════════════════════════════════════════════════════════════
# MachinePool (catalogue)
# ══════════════════════════════════════════════════════════════════════


class CreateMachinePoolCommand(BaseModel):
    name: str = Field(..., min_length=1)
    machine_ids: list[int] = Field(default_factory=list)
    note: str | None = None


class UpdateMachinePoolCommand(BaseModel):
    name: str | None = None
    machine_ids: list[int] | None = None
    note: str | None = None


class MachinePoolResult(ResultBase):
    created: datetime
    changed: datetime | None
    archived: bool
    name: str
    machine_ids: list[int] = Field(default_factory=list)
    machines: list[ProductionMachineResult] = Field(default_factory=list)
    note: str | None
    creator_id: int
    creator_full_name: str = ""
    changed_by_id: int | None
    changed_by_full_name: str | None
    changes: list[str] = Field(default_factory=list)
