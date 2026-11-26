"""Read models and commands for the schedule board and Auto-Plan."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from datetime import datetime
from typing import Literal

from pydantic import BaseModel
from pydantic import Field

from src.modules.fulfillment.domain.services.scheduling.placement_reason import PlacementReasonKind
from src.modules.fulfillment.domain.value_objects.auto_plan_algorithm import AutoPlanAlgorithm

# ══════════════════════════════════════════════════════════════════════
# Schedule board
# ══════════════════════════════════════════════════════════════════════


class ScheduleBoardOrderResult(BaseModel):
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
    status: str
    pinned: bool
    planned_start: datetime | None
    planned_end: datetime | None
    lot_position_sequence: int
    lot_position_count: int
    conflicts: list[str] = Field(default_factory=list)
    machine_pool_id: int | None = None
    # Pool-assigned without a machine yet; its time is held provisionally
    # on trial_machine_id.
    is_floating: bool = False
    # A forecast only, never persisted onto the order.
    trial_machine_id: int | None = None


class MachineCapacityDayResult(BaseModel):
    date: date
    booked_minutes: int
    available_minutes: int
    # A real overlap such as colliding pinned windows, not high utilization.
    overbooked_minutes: int = 0


class ScheduleBoardMachineResult(BaseModel):
    machine_id: int
    machine_internal_name: str
    orders: list[ScheduleBoardOrderResult] = Field(default_factory=list)
    capacity: list[MachineCapacityDayResult] = Field(default_factory=list)


class ScheduleBoardPoolResult(BaseModel):
    """A pool's combined available/booked time, rolled up from
    its member machines' own already-computed calendars (see
    GetScheduleBoard), plus every order currently tied to the pool
    (resolved or not) so a planner can see "12 items for pool Milling
    Machines" at a glance without drilling into each member machine."""

    pool_id: int
    pool_name: str
    machine_ids: list[int] = Field(default_factory=list)
    orders: list[ScheduleBoardOrderResult] = Field(default_factory=list)
    capacity: list[MachineCapacityDayResult] = Field(default_factory=list)


class ScheduleBoardResult(BaseModel):
    machines: list[ScheduleBoardMachineResult] = Field(default_factory=list)
    pools: list[ScheduleBoardPoolResult] = Field(default_factory=list)
    unassigned: list[ScheduleBoardOrderResult] = Field(default_factory=list)
    # Since when the stored planned dates await a background walk; the board
    # itself walks on read and is current. None when no walk is pending.
    stale_since: datetime | None = None


# ══════════════════════════════════════════════════════════════════════
# Auto-planner
# ══════════════════════════════════════════════════════════════════════


class AutoPlanCommand(BaseModel):
    machine_ids: list[int] | None = None  # None = every machine
    lot_id: int | None = None  # optionally scope to one lot's orders only
    # The run options are described in docs/reference/scheduling.md.
    assign_machines: bool = False
    planning_level: Literal["machines", "pools"] = "machines"
    overwrite_pinned: bool = False
    exclude_todays_planned: bool = True
    algorithm: str = AutoPlanAlgorithm.default().value
    # Overrides the global response-time buffer for this run only.
    response_time_days: int | None = Field(default=None, ge=0)


class AutoPlanOrderDiff(BaseModel):
    order_id: int
    production_order_number: str
    lot_number: str
    made_item_part_number: str
    made_item_revision: str
    before_machine_id: int | None
    after_machine_id: int | None
    # → MachinePool, so the diff table can show a pool move.
    before_machine_pool_id: int | None = None
    after_machine_pool_id: int | None = None
    before_queue_sequence: int
    after_queue_sequence: int
    before_planned_start: datetime | None
    before_planned_end: datetime | None
    after_planned_start: datetime | None
    after_planned_end: datetime | None
    conflicts: list[str] = Field(default_factory=list)


class AutoPlanSkippedOrder(BaseModel):
    """One candidate AutoPlan's placement loop declined to place, see
    AutoPlanSkipReason for the possible reasons. Distinct from the
    skipped_pinned_or_in_progress/skipped_todays_planned counters below:
    those are anchors that were never candidates at all, this is a real
    candidate the loop considered and could not place."""

    order_id: int
    production_order_number: str
    reason: str  # AutoPlanSkipReason


# The board column an order sits in, as the queue board groups it.
BoardColumn = Literal["machine", "pool", "manual", "inspection", "unassigned"]


class RedatedOrderReason(BaseModel):
    """Why the walk dated a re-dated order where it did
    (scheduling.PlacementReason), with what it refers to resolved for the
    planner. Each field is set only for the kinds that name it."""

    kind: PlacementReasonKind
    day: date | None = None
    moment: datetime | None = None
    # queue: the order ahead on the queue, and when it runs, its progress.
    previous_order_id: int | None = None
    previous_order_number: str | None = None
    previous_running: bool = False
    previous_overrun: bool = False
    previous_pieces_processed: float | None = None
    previous_quantity: float | None = None
    # predecessor and order_line: the earlier position, its latest order and
    # the method of its last step, whose wait it is.
    predecessor_sequence: int | None = None
    predecessor_order_number: str | None = None
    method_name: dict[str, str] = Field(default_factory=dict)
    wait_after_minutes: int = 0
    # order_line: the line and the day it is expected, late once passed,
    # the day it arrived once it did, or the forecast without a supplier date.
    order_item_id: int | None = None
    expected_date: date | None = None
    late: bool = False
    arrived: bool = False
    forecast: bool = False
    response_time_days: int = 0
    # in_progress: the order's own progress.
    pieces_processed: float | None = None
    quantity: float | None = None
    overrun: bool = False


class RedatedOrder(BaseModel):
    """An open order the walk after Auto-Plan moved to another day without
    Auto-Plan placing it, with its window before and after the walk."""

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
    reason: RedatedOrderReason | None = None


class AutoPlanResult(BaseModel):
    proposals: list[AutoPlanOrderDiff] = Field(default_factory=list)
    skipped_pinned_or_in_progress: int = 0
    skipped_todays_planned: int = 0
    skipped: list[AutoPlanSkippedOrder] = Field(default_factory=list)
    # The orders the walk after the run moved to another day without the run
    # placing them, and how many other open orders kept their day.
    redated: list[RedatedOrder] = Field(default_factory=list)
    kept_day: int = 0
    # The walk after the run failed, so the dates were not refreshed.
    walk_failed: bool = False


# ══════════════════════════════════════════════════════════════════════
# Auto-planner live progress (SSE). Plain dataclasses, because the stream
# endpoint serializes them directly without pydantic validation.
# ══════════════════════════════════════════════════════════════════════


@dataclass
class AutoPlanProgressOrder:
    order_id: int
    production_order_number: str
    lot_number: str
    made_item_part_number: str
    made_item_revision: str
    placed: bool
    before_machine_id: int | None
    after_machine_id: int | None
    before_machine_pool_id: int | None
    after_machine_pool_id: int | None
    # AutoPlanSkipReason, only ever set on a placed=False frame (None on a
    # placed=True one, and on the manual-step pools-mode skip, which isn't
    # a reported AutoPlanSkippedOrder case, see AutoPlan._place_candidates).
    reason: str | None = None


# The phases an auto-plan run reports in its progress events and status.
AutoPlanStage = Literal[
    "preparing", "loading_orders", "scoring", "placing", "recomputing", "finalizing"
]


@dataclass
class AutoPlanProgress:
    stage: AutoPlanStage
    current: int | None = None
    total: int | None = None
    order: AutoPlanProgressOrder | None = None


AutoPlanProgressCallback = Callable[[AutoPlanProgress], None]
