"""
HTTP schemas for the production schedule board and auto-planner.
"""

from datetime import date
from datetime import datetime
from typing import Literal

from fastapi import Query
from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field
from pydantic import model_validator

from src.modules.fulfillment.application.dto.production_schedule_dto import AutoPlanStage
from src.modules.fulfillment.application.dto.production_schedule_dto import BoardColumn
from src.modules.fulfillment.domain.services.scheduling.placement_reason import PlacementReasonKind
from src.modules.fulfillment.domain.value_objects.auto_plan_algorithm import AutoPlanAlgorithm
from src.modules.fulfillment.domain.value_objects.auto_plan_skip_reason import AutoPlanSkipReason
from src.modules.fulfillment.domain.value_objects.production_status import ProductionOrderStatus
from src.modules.fulfillment.domain.value_objects.schedule_conflict import ScheduleConflictReason
from src.modules.platform.adapters.inbound.api.schemas.base import ResponseModel
from src.modules.platform.domain.exceptions import InvalidInputError

# The board computes capacity per day and order, so its range is bounded.
MAX_BOARD_DAYS = 731


class ScheduleBoardFilterParams(BaseModel):
    date_from: date = Query(...)
    date_to: date = Query(...)

    # A domain error, not a ValueError, as in the KPI filter.
    @model_validator(mode="after")
    def _a_bounded_range(self) -> "ScheduleBoardFilterParams":
        if self.date_to < self.date_from:
            raise InvalidInputError("date_to must not lie before date_from.")
        if (self.date_to - self.date_from).days >= MAX_BOARD_DAYS:
            raise InvalidInputError(f"The board covers at most {MAX_BOARD_DAYS} days.")
        return self


class ScheduleBoardOrderResponse(ResponseModel):
    order_id: int
    production_order_number: str
    lot_id: int
    lot_number: str
    project_number: str
    made_item_id: int
    made_item_part_number: str
    made_item_revision: str
    quantity: float
    queue_sequence: int
    status: ProductionOrderStatus
    pinned: bool
    planned_start: datetime | None
    planned_end: datetime | None
    lot_position_sequence: int
    lot_position_count: int
    conflicts: list[ScheduleConflictReason] = Field(default_factory=list)
    machine_pool_id: int | None = None
    # True iff pool-assigned but not yet resolved to a concrete machine
    # (machine_id is None and machine_pool_id is not None): a floating
    # reservation, see trial_machine_id below.
    is_floating: bool = False
    # The pool member machine this floating order's time is provisionally
    # held against: a scheduling forecast, never persisted onto the
    # order. None for machine-assigned/manual/unassigned orders.
    trial_machine_id: int | None = None

    model_config = ConfigDict(from_attributes=True)


class MachineCapacityDayResponse(ResponseModel):
    date: date
    booked_minutes: int
    available_minutes: int
    # max(0, booked_minutes - available_minutes), a real overlap, not
    # merely high utilization.
    overbooked_minutes: int = 0

    model_config = ConfigDict(from_attributes=True)


class ScheduleBoardMachineResponse(ResponseModel):
    machine_id: int
    machine_internal_name: str
    orders: list[ScheduleBoardOrderResponse] = Field(default_factory=list)
    capacity: list[MachineCapacityDayResponse] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class ScheduleBoardPoolResponse(ResponseModel):
    pool_id: int
    pool_name: str
    machine_ids: list[int] = Field(default_factory=list)
    orders: list[ScheduleBoardOrderResponse] = Field(default_factory=list)
    capacity: list[MachineCapacityDayResponse] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class ScheduleBoardResponse(ResponseModel):
    machines: list[ScheduleBoardMachineResponse] = Field(default_factory=list)
    pools: list[ScheduleBoardPoolResponse] = Field(default_factory=list)
    unassigned: list[ScheduleBoardOrderResponse] = Field(default_factory=list)
    stale_since: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class AutoPlanRequest(BaseModel):
    # extra="forbid": an unknown field such as an assign_pool_machines bool
    # (planning_level below has no alias for it) must be REJECTED outright
    # rather than silently ignored, so a stale client sending it gets a 422
    # instead of a request that quietly doesn't do what it asked for.
    model_config = {"extra": "forbid"}

    machine_ids: list[int] | None = None
    lot_id: int | None = Field(default=None, gt=0)
    assign_machines: bool = False
    planning_level: Literal["machines", "pools"] = "machines"
    overwrite_pinned: bool = False
    exclude_todays_planned: bool = True
    algorithm: str = AutoPlanAlgorithm.default().value
    response_time_days: int | None = Field(default=None, ge=0)


class AutoPlanOrderDiffResponse(ResponseModel):
    order_id: int
    production_order_number: str
    lot_number: str
    made_item_part_number: str
    made_item_revision: str
    before_machine_id: int | None
    after_machine_id: int | None
    before_machine_pool_id: int | None = None
    after_machine_pool_id: int | None = None
    before_queue_sequence: int
    after_queue_sequence: int
    before_planned_start: datetime | None
    before_planned_end: datetime | None
    after_planned_start: datetime | None
    after_planned_end: datetime | None
    conflicts: list[ScheduleConflictReason] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class AutoPlanSkippedOrderResponse(ResponseModel):
    order_id: int
    production_order_number: str
    reason: AutoPlanSkipReason

    model_config = ConfigDict(from_attributes=True)


class RedatedOrderReasonResponse(ResponseModel):
    kind: PlacementReasonKind
    day: date | None
    moment: datetime | None
    previous_order_id: int | None
    previous_order_number: str | None
    previous_running: bool
    previous_overrun: bool
    previous_pieces_processed: float | None
    previous_quantity: float | None
    predecessor_sequence: int | None
    predecessor_order_number: str | None
    method_name: dict[str, str]
    wait_after_minutes: int
    order_item_id: int | None
    expected_date: date | None
    late: bool
    arrived: bool
    forecast: bool
    response_time_days: int
    pieces_processed: float | None
    quantity: float | None
    overrun: bool

    model_config = ConfigDict(from_attributes=True)


class RedatedOrderResponse(ResponseModel):
    order_id: int
    production_order_number: str
    lot_id: int | None
    lot_number: str
    made_item_part_number: str
    made_item_revision: str
    column: BoardColumn
    machine_id: int | None
    machine_pool_id: int | None
    before_planned_start: datetime | None
    before_planned_end: datetime | None
    after_planned_start: datetime | None
    after_planned_end: datetime | None
    reason: RedatedOrderReasonResponse | None

    model_config = ConfigDict(from_attributes=True)


class AutoPlanResponse(ResponseModel):
    proposals: list[AutoPlanOrderDiffResponse] = Field(default_factory=list)
    skipped_pinned_or_in_progress: int = 0
    skipped_todays_planned: int = 0
    skipped: list[AutoPlanSkippedOrderResponse] = Field(default_factory=list)
    redated: list[RedatedOrderResponse] = Field(default_factory=list)
    kept_day: int = 0
    walk_failed: bool = False

    model_config = ConfigDict(from_attributes=True)


class AutoPlanRunResponse(ResponseModel):
    """The auto-plan run in progress and who started it. `stage`, `current`
    and `total` are the progress the runner's own stream shows, so a poll
    shows the same numbers."""

    run_id: str
    user_id: int
    user_name: str
    started_at: str
    stage: AutoPlanStage | None
    current: int | None
    total: int | None

    model_config = ConfigDict(from_attributes=True)


class AutoPlanRunStatusResponse(ResponseModel):
    """GET /auto-plan/status: the source of truth for every client that
    isn't the runner itself; late joiners, page reloads, reconnects,
    and the observer dialog's poll all recover through this rather than
    depending on having received a live signal."""

    running: bool
    run: AutoPlanRunResponse | None

    model_config = ConfigDict(from_attributes=True)
