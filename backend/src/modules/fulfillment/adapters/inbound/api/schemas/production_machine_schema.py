"""
HTTP schemas for the ProductionMachine catalogue aggregate.
"""

from datetime import date
from datetime import datetime
from typing import Literal

from fastapi import Query
from pydantic import BaseModel
from pydantic import Field

from src.modules.catalogue.application.dto.fabrication_method_dto import FabricationMethodResult
from src.modules.fulfillment.application.dto.machine_calendar_dto import DEFAULT_DAY_START
from src.modules.fulfillment.domain.value_objects.machine_downtime_reason import (
    MachineDowntimeReason,
)
from src.modules.fulfillment.domain.value_objects.production_machine_status import (
    ProductionMachineStatus,
)
from src.modules.fulfillment.domain.value_objects.production_status import ProductionOrderStatus
from src.modules.fulfillment.domain.value_objects.work_interval import CLOCK_PATTERN
from src.modules.fulfillment.domain.value_objects.work_interval import MINUTES_PER_DAY
from src.modules.fulfillment.ports.outbound.repositories.machine_downtime_repository import (
    MachineDowntimeFilterDto,
)
from src.modules.fulfillment.ports.outbound.repositories.production_machine_repository import (
    ProductionMachineFilterDto,
)
from src.modules.platform.adapters.inbound.api.schemas.base import EntityResponse
from src.modules.platform.adapters.inbound.api.schemas.base import ResponseModel
from src.modules.platform.adapters.inbound.api.schemas.pagination_schema import PageParams
from src.modules.platform.adapters.inbound.api.schemas.user_schema import PublicUserResponse

# ══════════════════════════════════════════════════════════════════════
# ProductionMachine (catalogue)
# ══════════════════════════════════════════════════════════════════════


class ProductionMachineCreateRequest(BaseModel):
    internal_name: str = Field(..., min_length=1)
    vendor: str = Field(..., min_length=1)
    model: str = Field(..., min_length=1)
    fabrication_method_ids: list[int] = Field(default_factory=list)
    max_part_dimension: str | None = None
    note: str | None = None
    is_qa_machine: bool = False


class ProductionMachineUpdateRequest(BaseModel):
    internal_name: str | None = Field(default=None, min_length=1)
    vendor: str | None = Field(default=None, min_length=1)
    model: str | None = Field(default=None, min_length=1)
    fabrication_method_ids: list[int] | None = None
    max_part_dimension: str | None = None
    note: str | None = None
    is_qa_machine: bool | None = None


class OpenMachineDowntimeResponse(ResponseModel):
    """Minimal shape denormalized onto ProductionMachineResponse so the
    machine list and detail views can show an open-downtime badge without
    a second round trip."""

    id: int
    started_at: datetime
    reason: MachineDowntimeReason


class ActiveProductionOrderResponse(ResponseModel):
    """Minimal shape denormalized onto ProductionMachineResponse so the
    machine list and detail views can show which orders are running or
    paused, for the status tag's tooltip, without a second round trip."""

    id: int
    production_order_number: str
    status: ProductionOrderStatus


class ProductionMachineResponse(EntityResponse):
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
    open_downtime: OpenMachineDowntimeResponse | None = None
    # Computed on read from open_downtime and active_orders, never stored.
    status: ProductionMachineStatus = ProductionMachineStatus.IDLE
    active_orders: list[ActiveProductionOrderResponse] = Field(default_factory=list)
    # Queued, in-progress and paused orders on the machine, which keep it
    # from being archived. Computed on read.
    live_order_count: int = 0


class ProductionMachineFilterParams(PageParams):
    search: str | None = Query(default=None, description="Fuzzy search across all text columns")
    id: int | None = Query(default=None)
    internal_name: str | None = Query(default=None)
    vendor: str | None = Query(default=None)
    model: str | None = Query(default=None)
    fabrication_method_id: int | None = Query(default=None)
    creator_id: int | None = Query(default=None)
    changed_by_id: int | None = Query(default=None)
    include_archived: bool = Query(default=False)
    order_by: Literal["id", "internal_name", "vendor", "model", "changed", "created"] | None = (
        Query(default=None)
    )
    order_dir: Literal["asc", "desc"] | None = Query(default=None)

    def to_dto(self) -> ProductionMachineFilterDto:
        return ProductionMachineFilterDto(**self.model_dump())


# ══════════════════════════════════════════════════════════════════════
# Machine calendar
# ══════════════════════════════════════════════════════════════════════


class WorkIntervalSchema(BaseModel):
    """Working time from a start in the tenant's local time ("HH:MM") for a
    number of minutes; it belongs to the day it starts on."""

    start: str = Field(..., pattern=CLOCK_PATTERN)
    minutes: int = Field(..., ge=0, le=MINUTES_PER_DAY)


class MachineWorkingHoursSetRequest(BaseModel):
    # weekday (0=Monday..6=Sunday) -> working intervals that day, none = off
    weekly_hours: dict[int, list[WorkIntervalSchema]]


class MachineWorkingHoursResponse(EntityResponse):
    created: datetime
    changed: datetime | None
    machine_id: int
    weekly_hours: dict[int, list[WorkIntervalSchema]]
    creator_id: int
    changed_by_id: int | None
    changed_by: PublicUserResponse | None


class MachineCalendarExceptionCreateRequest(BaseModel):
    exception_date: date
    available_minutes: int = Field(..., ge=0, le=MINUTES_PER_DAY)
    start: str = Field(default=DEFAULT_DAY_START, pattern=CLOCK_PATTERN)
    note: str | None = None


class MachineCalendarExceptionUpdateRequest(BaseModel):
    available_minutes: int = Field(..., ge=0, le=MINUTES_PER_DAY)
    start: str = Field(default=DEFAULT_DAY_START, pattern=CLOCK_PATTERN)
    note: str | None = None


class MachineCalendarExceptionResponse(EntityResponse):
    created: datetime
    changed: datetime | None
    machine_id: int
    exception_date: date
    available_minutes: int
    start: str
    note: str | None
    creator_id: int
    changed_by_id: int | None
    changed_by: PublicUserResponse | None


# ══════════════════════════════════════════════════════════════════════
# Machine downtime
# ══════════════════════════════════════════════════════════════════════


class MachineDowntimeCreateRequest(BaseModel):
    machine_id: int
    started_at: datetime
    ended_at: datetime | None = None
    reason: MachineDowntimeReason
    note: str | None = None


class MachineDowntimeUpdateRequest(BaseModel):
    started_at: datetime
    ended_at: datetime | None = None
    reason: MachineDowntimeReason
    note: str | None = None


class MachineDowntimeEndRequest(BaseModel):
    ended_at: datetime | None = None


class MachineDowntimeResponse(EntityResponse):
    created: datetime
    changed: datetime | None
    machine_id: int
    machine_internal_name: str
    started_at: datetime
    ended_at: datetime | None
    reason: MachineDowntimeReason
    note: str | None
    reported_by_id: int
    reported_by_full_name: str
    ended_by_id: int | None
    ended_by_full_name: str | None
    changed_by_id: int | None
    changed_by_full_name: str | None
    changes: list[str] = Field(default_factory=list)


class MachineDowntimeFilterParams(PageParams):
    machine_id: int | None = Query(default=None)
    reason: MachineDowntimeReason | None = Query(default=None)
    open_only: bool = Query(default=False)
    started_from: datetime | None = Query(default=None, description="Period filter start")
    started_to: datetime | None = Query(default=None, description="Period filter end")
    order_by: Literal["started_at", "machine_id"] | None = Query(default=None)
    order_dir: Literal["asc", "desc"] | None = Query(default=None)

    def to_dto(self) -> MachineDowntimeFilterDto:
        return MachineDowntimeFilterDto(
            skip=self.skip,
            limit=self.limit,
            machine_id=self.machine_id,
            reason=self.reason.value if self.reason else None,
            open_only=self.open_only,
            started_from=self.started_from,
            started_to=self.started_to,
            order_by=self.order_by,
            order_dir=self.order_dir,
        )
