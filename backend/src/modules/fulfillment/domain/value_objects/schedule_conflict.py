"""
Conflict flags produced by the scheduling package. The scheduler
always computes and places an order, "planner sets order, system shows
conflicts", never blocks on any of these.
"""

from enum import unique

from src.shared_kernel.domain.value_objects.value_enum import StrValueEnum


@unique
class ScheduleConflictReason(StrValueEnum):
    # No machine has been picked at all yet (ProductionOrder.machine_id is
    # None), distinct from CAPABILITY_MISMATCH, where a machine is picked
    # but doesn't cover the position's required fabrication method(s).
    NO_MACHINE_ASSIGNED = "no_machine_assigned"
    CAPABILITY_MISMATCH = "capability_mismatch"
    UNCATEGORIZED_STEP = "uncategorized_step"
    POSITION_NOT_FULLY_QUEUED = "position_not_fully_queued"
    WAITING_ON_PREDECESSOR = "waiting_on_predecessor"
    # The sequence-1 twin of WAITING_ON_PREDECESSOR: a sequence-1 INTERNAL/
    # MIXED position whose raw material hasn't arrived (no demand linked,
    # demand not allocated, or allocated but nothing delivered). Raised
    # regardless of whether a delivery forecast exists: StartProduction
    # Order refuses to start/resume either way until material actually
    # arrives, this just mirrors that gate as a badge. Dates: when a
    # forecast exists too (material_ready_at is set), the order is still
    # placed, floored at that date; with no forecast either,
    # scheduling.advance_machine_queue additionally leaves the
    # order undated rather than fabricate one (see
    # is_unplannable_for_missing_material).
    WAITING_ON_MATERIAL = "waiting_on_material"
    # Soft, duration includes at least one step using the time-budget
    # fallback rather than a real measurement.
    ESTIMATE_FROM_TIME_BUDGET = "estimate_from_time_budget"
    # No real estimate and no time-budget fallback either, the
    # contributing figure is a bare 0, the least trustworthy case.
    MISSING_TIME_ESTIMATE = "missing_time_estimate"
    PAST_TARGET_DATE = "past_target_date"
    # An EXTERNAL or MIXED position's typed date (expected delivery, or
    # expected pickup when no expected delivery is set) is earlier than the
    # chain feeding it, flagged on the first INTERNAL or MIXED position
    # after that stale predecessor. The scheduler never rewrites or clears
    # the typed date, this only surfaces the contradiction for a person to
    # resolve. Never raised once an actual delivery or ready-for-pickup
    # date exists, those are facts rather than promises.
    EXTERNAL_DATE_BEFORE_PREDECESSOR = "external_date_before_predecessor"
    # The order's assigned machine has an open downtime right now (see
    # machine_downtime_table/IMachineDowntimeRepository.get_open_by_machine_ids).
    # Raised for every non-terminal order on that machine regardless of its
    # planned dates, informational only like every other reason here; the
    # scheduler still places the order, it just also reports the machine
    # isn't actually available.
    MACHINE_DOWN = "machine_down"
    # The machine's calendar holds no working time to place the order in,
    # such as a week of zero hours or a downtime that never ends. Only that
    # machine's queue stays undated; a machine may be out of service.
    NO_WORKING_TIME = "no_working_time"
    # A pinned or frozen window starts before the previous order on its
    # queue ends. The window is kept, as a pin asks, and the next order
    # starts after both.
    WINDOW_OVERLAP = "window_overlap"
    # A pinned or frozen window starts before the previous step of its lot is
    # ready, so its pieces cannot be there yet. The window is kept, as a pin
    # asks; the next step still waits for this one's end.
    WINDOW_BEFORE_PREDECESSOR = "window_before_predecessor"
    # The order is on a cycle of waits, such as a step queued ahead of its own
    # predecessor on one machine, or waits on such a cycle. It stays undated
    # until someone reorders the queue, since every date would run away.
    CHAIN_CYCLE = "chain_cycle"
