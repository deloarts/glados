"""
HTTP schemas for the MachinePool catalogue aggregate.
"""

from datetime import datetime
from typing import Literal

from fastapi import Query
from pydantic import BaseModel
from pydantic import Field

from src.modules.fulfillment.application.dto.production_machine_dto import ProductionMachineResult
from src.modules.fulfillment.ports.outbound.repositories.machine_pool_repository import (
    MachinePoolFilterDto,
)
from src.modules.platform.adapters.inbound.api.schemas.base import EntityResponse
from src.modules.platform.adapters.inbound.api.schemas.pagination_schema import PageParams

# ══════════════════════════════════════════════════════════════════════
# MachinePool (catalogue)
# ══════════════════════════════════════════════════════════════════════


class MachinePoolCreateRequest(BaseModel):
    name: str = Field(..., min_length=1)
    machine_ids: list[int] = Field(default_factory=list)
    note: str | None = None


class MachinePoolUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1)
    machine_ids: list[int] | None = None
    note: str | None = None


class MachinePoolResponse(EntityResponse):
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


class MachinePoolFilterParams(PageParams):
    search: str | None = Query(default=None, description="Fuzzy search across all text columns")
    id: int | None = Query(default=None)
    name: str | None = Query(default=None)
    machine_id: int | None = Query(default=None)
    creator_id: int | None = Query(default=None)
    changed_by_id: int | None = Query(default=None)
    include_archived: bool = Query(default=False)
    order_by: Literal["id", "name", "changed", "created"] | None = Query(default=None)
    order_dir: Literal["asc", "desc"] | None = Query(default=None)

    def to_dto(self) -> MachinePoolFilterDto:
        return MachinePoolFilterDto(**self.model_dump())
