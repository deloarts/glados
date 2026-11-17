"""
DTOs for the ProductionMachine catalogue aggregate.
"""

from datetime import datetime

from pydantic import BaseModel
from pydantic import Field

from src.modules.catalogue.application.dto.fabrication_method_dto import FabricationMethodResult
from src.modules.fulfillment.application.dto.machine_downtime_dto import OpenMachineDowntimeResult
from src.modules.fulfillment.domain.value_objects.production_machine_status import (
    ProductionMachineStatus,
)
from src.modules.fulfillment.domain.value_objects.production_status import ProductionOrderStatus
from src.modules.platform.application.dto.base import ResultBase
from src.modules.platform.application.dto.base import ResultModel

# ══════════════════════════════════════════════════════════════════════
# ProductionMachine (catalogue)
# ══════════════════════════════════════════════════════════════════════


class CreateProductionMachineCommand(BaseModel):
    internal_name: str = Field(..., min_length=1)
    vendor: str = Field(..., min_length=1)
    model: str = Field(..., min_length=1)
    fabrication_method_ids: list[int] = Field(default_factory=list)
    max_part_dimension: str | None = None
    note: str | None = None
    is_qa_machine: bool = False


class UpdateProductionMachineCommand(BaseModel):
    internal_name: str | None = None
    vendor: str | None = None
    model: str | None = None
    fabrication_method_ids: list[int] | None = None
    max_part_dimension: str | None = None
    note: str | None = None
    is_qa_machine: bool | None = None


class ActiveProductionOrderResult(ResultModel):
    """A running or paused production order on a machine, embedded in the
    machine so the list and detail views need no second request."""

    id: int
    production_order_number: str
    status: ProductionOrderStatus


class ProductionMachineResult(ResultBase):
    created: datetime
    changed: datetime | None
    archived: bool
    internal_name: str
    vendor: str
    model: str
    fabrication_method_ids: list[int] = Field(default_factory=list)
    fabrication_methods: list[FabricationMethodResult] = Field(default_factory=list)
    max_part_dimension: str | None
    note: str | None
    is_qa_machine: bool = False
    creator_id: int
    creator_full_name: str = ""
    changed_by_id: int | None
    changed_by_full_name: str | None
    changes: list[str] = Field(default_factory=list)
    open_downtime: OpenMachineDowntimeResult | None = None
    # Computed on read, never stored; see resolve_machine_status.
    status: ProductionMachineStatus = ProductionMachineStatus.IDLE
    active_orders: list[ActiveProductionOrderResult] = Field(default_factory=list)
    # Queued, in-progress and paused orders on the machine, which keep it
    # from being archived. Computed on read.
    live_order_count: int = 0
