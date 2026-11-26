"""Pure domain service for deep scheduling and Auto-Plan. The rules are
summarized in docs/reference/scheduling.md.

The calling use case flattens pre-fetched entities into small context
dataclasses; this package returns plain values and never does I/O. Instants
are timezone-aware UTC, while every calendar day is a day of the tenant's
timezone, which the caller passes in: a calendar's hours, readiness, target
and not_before dates, and the day an instant falls on. machine_calendar resolves working time,
earliest_start and walk_context derive when an order may start,
forward_walk dates every queue, capacity sums the board's booked minutes,
and candidate_ordering and machine_selection hold Auto-Plan's ordering and
placement choices. Every public name is re-exported here, so callers import
from `src.modules.fulfillment.domain.services.scheduling`.
"""

from src.modules.fulfillment.domain.policies.wait_after import StepWait
from src.modules.fulfillment.domain.policies.wait_after import latest_ready_moment
from src.modules.fulfillment.domain.policies.wait_after import position_wait_after_minutes
from src.modules.fulfillment.domain.policies.wait_after import ready_after_wait
from src.modules.fulfillment.domain.policies.wait_after import step_waits
from src.modules.fulfillment.domain.policies.wait_after import wait_days
from src.modules.fulfillment.domain.services.scheduling.candidate_ordering import AutoPlanCandidate
from src.modules.fulfillment.domain.services.scheduling.candidate_ordering import OrderingStrategy
from src.modules.fulfillment.domain.services.scheduling.candidate_ordering import (
    compute_position_due_dates,
)
from src.modules.fulfillment.domain.services.scheduling.candidate_ordering import position_lead_days
from src.modules.fulfillment.domain.services.scheduling.candidate_ordering import (
    production_order_touches_date,
)
from src.modules.fulfillment.domain.services.scheduling.candidate_ordering import sort_candidates
from src.modules.fulfillment.domain.services.scheduling.candidate_ordering import (
    sort_candidates_by_critical_ratio,
)
from src.modules.fulfillment.domain.services.scheduling.candidate_ordering import (
    sort_candidates_by_edd,
)
from src.modules.fulfillment.domain.services.scheduling.candidate_ordering import (
    sort_candidates_by_fifo,
)
from src.modules.fulfillment.domain.services.scheduling.candidate_ordering import (
    sort_candidates_by_priority,
)
from src.modules.fulfillment.domain.services.scheduling.candidate_ordering import (
    sort_candidates_by_spt,
)
from src.modules.fulfillment.domain.services.scheduling.capacity import compute_daily_capacity
from src.modules.fulfillment.domain.services.scheduling.earliest_start import compute_earliest_start
from src.modules.fulfillment.domain.services.scheduling.earliest_start import (
    resolve_external_predecessor_ready_at,
)
from src.modules.fulfillment.domain.services.scheduling.earliest_start import (
    resolve_input_material_ready_at,
)
from src.modules.fulfillment.domain.services.scheduling.earliest_start import (
    resolve_internal_predecessor_ready_at,
)
from src.modules.fulfillment.domain.services.scheduling.earliest_start import (
    resolve_mixed_predecessor_ready_at,
)
from src.modules.fulfillment.domain.services.scheduling.forward_walk import EarliestStartExplanation
from src.modules.fulfillment.domain.services.scheduling.forward_walk import EarliestStartReason
from src.modules.fulfillment.domain.services.scheduling.forward_walk import ScheduleWalkResult
from src.modules.fulfillment.domain.services.scheduling.forward_walk import advance_machine_queue
from src.modules.fulfillment.domain.services.scheduling.forward_walk import compute_order_conflicts
from src.modules.fulfillment.domain.services.scheduling.forward_walk import explain_earliest_start
from src.modules.fulfillment.domain.services.scheduling.forward_walk import (
    is_unplannable_for_missing_material,
)
from src.modules.fulfillment.domain.services.scheduling.forward_walk import placed_ends_by_position
from src.modules.fulfillment.domain.services.scheduling.forward_walk import propagation_pass_limit
from src.modules.fulfillment.domain.services.scheduling.forward_walk import schedule_all
from src.modules.fulfillment.domain.services.scheduling.forward_walk import schedule_all_propagated
from src.modules.fulfillment.domain.services.scheduling.forward_walk import (
    schedule_unassigned_orders,
)
from src.modules.fulfillment.domain.services.scheduling.machine_calendar import MachineCalendar
from src.modules.fulfillment.domain.services.scheduling.machine_calendar import apply_downtimes
from src.modules.fulfillment.domain.services.scheduling.machine_calendar import (
    build_machine_calendar,
)
from src.modules.fulfillment.domain.services.scheduling.machine_calendar import place
from src.modules.fulfillment.domain.services.scheduling.machine_calendar import (
    resolve_weekly_minutes,
)
from src.modules.fulfillment.domain.services.scheduling.machine_calendar import (
    snap_to_working_start,
)
from src.modules.fulfillment.domain.services.scheduling.machine_calendar import validate_day_hours
from src.modules.fulfillment.domain.services.scheduling.machine_calendar import (
    validate_weekly_hours,
)
from src.modules.fulfillment.domain.services.scheduling.machine_selection import SelectionStrategy
from src.modules.fulfillment.domain.services.scheduling.machine_selection import (
    machine_covers_fabrication_methods,
)
from src.modules.fulfillment.domain.services.scheduling.machine_selection import (
    resolve_algorithm_strategies,
)
from src.modules.fulfillment.domain.services.scheduling.machine_selection import (
    resolve_best_machine,
)
from src.modules.fulfillment.domain.services.scheduling.machine_selection import resolve_best_pool
from src.modules.fulfillment.domain.services.scheduling.machine_selection import (
    resolve_eligible_machine_ids,
)
from src.modules.fulfillment.domain.services.scheduling.machine_selection import (
    resolve_eligible_pool_ids,
)
from src.modules.fulfillment.domain.services.scheduling.machine_selection import (
    resolve_least_loaded_machine,
)
from src.modules.fulfillment.domain.services.scheduling.machine_selection import (
    resolve_least_loaded_pool,
)
from src.modules.fulfillment.domain.services.scheduling.machine_selection import (
    resolve_machine_for_candidate,
)
from src.modules.fulfillment.domain.services.scheduling.machine_selection import (
    resolve_pool_for_candidate,
)
from src.modules.fulfillment.domain.services.scheduling.walk_context import ExternalForecast
from src.modules.fulfillment.domain.services.scheduling.walk_context import LeadDaysSource
from src.modules.fulfillment.domain.services.scheduling.walk_context import OrderSchedulingContext
from src.modules.fulfillment.domain.services.scheduling.walk_context import PredecessorPosition
from src.modules.fulfillment.domain.services.scheduling.walk_context import ScheduledOrder
from src.modules.fulfillment.domain.services.scheduling.walk_context import buffered_ready_day
from src.modules.fulfillment.domain.services.scheduling.walk_context import position_ready_at_in_run
from src.modules.fulfillment.domain.services.scheduling.walk_context import predecessor_ready_moment
from src.modules.fulfillment.domain.services.scheduling.walk_context import (
    refresh_predecessor_readiness,
)
from src.modules.fulfillment.domain.services.scheduling.walk_context import (
    resolve_chain_external_forecasts,
)
from src.modules.fulfillment.domain.services.scheduling.walk_context import (
    resolve_external_forecast,
)
from src.modules.fulfillment.domain.services.scheduling.walk_context import (
    resolve_external_forecasts,
)
from src.modules.fulfillment.domain.services.scheduling.walk_context import (
    resolve_position_lead_days,
)
from src.modules.fulfillment.domain.services.scheduling.walk_context import (
    resolve_position_lead_days_with_source,
)
from src.modules.fulfillment.domain.services.scheduling.walk_context import (
    stale_external_predecessor,
)
from src.modules.fulfillment.domain.services.scheduling.walk_context import (
    stored_predecessor_readiness,
)
from src.modules.fulfillment.domain.value_objects.work_interval import DayHours
from src.modules.fulfillment.domain.value_objects.work_interval import WorkInterval
from src.shared_kernel.domain.services.clock import as_utc

__all__ = [
    "AutoPlanCandidate",
    "DayHours",
    "EarliestStartExplanation",
    "EarliestStartReason",
    "ExternalForecast",
    "LeadDaysSource",
    "MachineCalendar",
    "OrderSchedulingContext",
    "OrderingStrategy",
    "PredecessorPosition",
    "ScheduleWalkResult",
    "ScheduledOrder",
    "SelectionStrategy",
    "StepWait",
    "WorkInterval",
    "advance_machine_queue",
    "apply_downtimes",
    "as_utc",
    "buffered_ready_day",
    "build_machine_calendar",
    "compute_daily_capacity",
    "compute_earliest_start",
    "compute_order_conflicts",
    "compute_position_due_dates",
    "explain_earliest_start",
    "is_unplannable_for_missing_material",
    "latest_ready_moment",
    "machine_covers_fabrication_methods",
    "place",
    "placed_ends_by_position",
    "position_lead_days",
    "position_ready_at_in_run",
    "position_wait_after_minutes",
    "predecessor_ready_moment",
    "production_order_touches_date",
    "propagation_pass_limit",
    "ready_after_wait",
    "refresh_predecessor_readiness",
    "resolve_algorithm_strategies",
    "resolve_best_machine",
    "resolve_best_pool",
    "resolve_chain_external_forecasts",
    "resolve_eligible_machine_ids",
    "resolve_eligible_pool_ids",
    "resolve_external_forecast",
    "resolve_external_forecasts",
    "resolve_external_predecessor_ready_at",
    "resolve_input_material_ready_at",
    "resolve_internal_predecessor_ready_at",
    "resolve_least_loaded_machine",
    "resolve_least_loaded_pool",
    "resolve_machine_for_candidate",
    "resolve_mixed_predecessor_ready_at",
    "resolve_pool_for_candidate",
    "resolve_position_lead_days",
    "resolve_position_lead_days_with_source",
    "resolve_weekly_minutes",
    "schedule_all",
    "schedule_all_propagated",
    "schedule_unassigned_orders",
    "snap_to_working_start",
    "sort_candidates",
    "sort_candidates_by_critical_ratio",
    "sort_candidates_by_edd",
    "sort_candidates_by_fifo",
    "sort_candidates_by_priority",
    "sort_candidates_by_spt",
    "stale_external_predecessor",
    "step_waits",
    "stored_predecessor_readiness",
    "validate_day_hours",
    "validate_weekly_hours",
    "wait_days",
]
