"""
A recorded production plan: one version of the dates the active scheduler
had for the orders inside the committed horizon, with one row per order and
one per lot. The nightly baseline is one such version per day, the
reference for how far the dates later moved.

The rows copy what identifies an order and a lot at recording time, so a
plan still reads after the order or the lot is deleted; the references
then turn empty.
"""

from dataclasses import dataclass
from dataclasses import field
from datetime import date
from datetime import datetime

from src.modules.fulfillment.domain.value_objects.plan_kind import PlanKind
from src.modules.fulfillment.domain.value_objects.plan_kind import PlanStatus
from src.modules.fulfillment.domain.value_objects.plan_kind import SchedulerMode
from src.shared_kernel.domain.entities.base import Entity

# The engine whose dates the current scheduler mode persists.
FORWARD_WALK_ENGINE = "forward_walk"
FORWARD_WALK_ENGINE_VERSION = "1"


@dataclass
class ProductionPlanEntry(Entity):
    """One order of a plan with the window the scheduler gave it."""

    production_order_id: int | None  # → ProductionOrder; None once it is deleted
    lot_position_id: int | None  # → LotPosition; None once it is deleted
    lot_id: int
    position_sequence: int
    production_order_number: str
    machine_id: int | None
    machine_pool_id: int | None
    queue_sequence: int
    planned_start: datetime
    planned_end: datetime | None
    # The duration the order was dated with.
    duration_minutes: int


@dataclass
class ProductionPlanLot(Entity):
    """One lot of a plan: its target date and when its last step's pieces
    were planned to be ready, the latest planned end plus the wait after its
    position over the orders the scheduler dated."""

    lot_id: int | None  # → ProductionLot; None once it is deleted
    lot_number: str
    target_date: date | None
    planned_finish: datetime | None


@dataclass
class ProductionPlan(Entity):
    kind: PlanKind
    scheduler_mode: SchedulerMode
    engine: str
    engine_version: str
    # The tenant day the plan was recorded for.
    plan_day: date
    created: datetime
    status: PlanStatus
    entries: list[ProductionPlanEntry] = field(default_factory=list)
    lots: list[ProductionPlanLot] = field(default_factory=list)
