"""Auto-Plan's choice of the machine or pool a candidate order is placed on.

Eligibility decides which machines and pools may take a candidate at all,
by fabrication-method coverage and the QA gate. Each SelectionStrategy then
picks one of them and advances its cursor through the forward walk's
advance_machine_queue, the same placement step the walk itself uses.
"""

from datetime import UTC
from datetime import datetime
from enum import Enum

from src.modules.fulfillment.domain.services.scheduling.candidate_ordering import OrderingStrategy
from src.modules.fulfillment.domain.services.scheduling.forward_walk import advance_machine_queue
from src.modules.fulfillment.domain.services.scheduling.machine_calendar import MachineCalendar
from src.modules.fulfillment.domain.services.scheduling.walk_context import OrderSchedulingContext
from src.modules.fulfillment.domain.value_objects.auto_plan_algorithm import AutoPlanAlgorithm


class SelectionStrategy(str, Enum):
    """Internal machine-selection strategy. See OrderingStrategy."""

    EARLIEST_FINISH = "earliest_finish"
    LEAST_LOADED = "least_loaded"


def machine_covers_fabrication_methods(
    machine_fabrication_method_ids: list[int],
    required_fabrication_method_ids: set[int],
) -> bool:
    """Boolean form of production_order_rules.assert_capability_match."""
    return required_fabrication_method_ids <= set(machine_fabrication_method_ids)


def resolve_eligible_machine_ids(
    *,
    order_machine_pool_id: int | None,
    order_machine_id: int | None,
    candidate_machine_ids: set[int],
    pool_machine_ids: set[int],
    machine_fabrication_method_ids: dict[int, list[int]],
    required_fabrication_method_ids: set[int],
    assign_pool_machines: bool,
    assign_machines: bool,
    qa_machine_ids: set[int] | None = None,
    requires_qa_machine: bool = False,
) -> list[int]:
    """Which machines Auto-Plan may trial a candidate order on.

    A pool-assigned order only ever resolves to the pool's capable members,
    gated by assign_pool_machines. An unassigned inspection order is never
    eligible: a QA machine is opt-in configuration through the inspection
    method's default machine, and without one the step is manual work that
    still gets dates from the manual queue. With assign_machines any
    capable machine qualifies; otherwise an order is only re-sequenced on
    the machine it already has.

    Inside every rule, inspection orders only go to QA machines and QA
    machines never take fabrication work.
    """
    qa_ids = qa_machine_ids or set()

    if order_machine_pool_id is not None and order_machine_id is None:
        if not assign_pool_machines:
            return []
        return [
            mid
            for mid in candidate_machine_ids
            if mid in pool_machine_ids
            and _machine_covers_candidate(
                mid,
                requires_qa_machine,
                qa_ids,
                machine_fabrication_method_ids,
                required_fabrication_method_ids,
            )
        ]

    if requires_qa_machine and order_machine_id is None:
        return []

    if assign_machines:
        return [
            mid
            for mid in candidate_machine_ids
            if _machine_covers_candidate(
                mid,
                requires_qa_machine,
                qa_ids,
                machine_fabrication_method_ids,
                required_fabrication_method_ids,
            )
        ]

    if (
        order_machine_id is not None
        and order_machine_id in candidate_machine_ids
        and _machine_covers_candidate(
            order_machine_id,
            requires_qa_machine,
            qa_ids,
            machine_fabrication_method_ids,
            required_fabrication_method_ids,
        )
    ):
        return [order_machine_id]
    return []


def _machine_covers_candidate(
    machine_id: int,
    requires_qa_machine: bool,
    qa_machine_ids: set[int],
    machine_fabrication_method_ids: dict[int, list[int]],
    required_fabrication_method_ids: set[int],
) -> bool:
    """QA gate plus fabrication-method coverage for one machine."""
    if requires_qa_machine != (machine_id in qa_machine_ids):
        return False
    if requires_qa_machine:
        return True
    return machine_covers_fabrication_methods(
        machine_fabrication_method_ids.get(machine_id, []), required_fabrication_method_ids
    )


def resolve_eligible_pool_ids(
    *,
    candidate_pool_ids: set[int],
    pool_machine_ids: dict[int, list[int]],
    machine_fabrication_method_ids: dict[int, list[int]],
    required_fabrication_method_ids: set[int],
    requires_qa_machine: bool = False,
    is_manual_step: bool = False,
) -> list[int]:
    """Which pools Auto-Plan may place a candidate into.

    A pool's capability is the intersection of its members' fabrication
    methods, as in production_order_rules.assert_pool_capability_match.
    Memberless pools, inspection positions and manual-step positions are
    never eligible, since an empty required set would otherwise match every
    pool vacuously."""
    if requires_qa_machine or is_manual_step:
        return []
    eligible = []
    for pool_id in candidate_pool_ids:
        member_ids = pool_machine_ids.get(pool_id, [])
        if not member_ids:
            continue
        derived = set.intersection(
            *(set(machine_fabrication_method_ids.get(mid, [])) for mid in member_ids)
        )
        if required_fabrication_method_ids <= derived:
            eligible.append(pool_id)
    return eligible


def resolve_best_machine(
    ctx: OrderSchedulingContext,
    eligible_machine_ids: list[int],
    machine_cursors: dict[int, datetime | None],
    calendars: dict[int, MachineCalendar],
    now: datetime,
    machine_queue_lengths: dict[int, int] | None = None,
) -> tuple[int, datetime | None] | None:
    """Greedy choice of the eligible machine that finishes the candidate
    soonest. Returns (machine_id, next_cursor), or None without eligible
    machines.

    An undated candidate ties on every machine, and picking the first one
    would pile every such candidate onto one machine. When all trials are
    undated, the shortest queue wins instead (then the lowest id).
    """
    best_machine_id: int | None = None
    best_end: datetime | None = None
    best_next_cursor: datetime | None = None
    sentinel = datetime.max.replace(tzinfo=UTC)
    all_sentinel = True
    next_cursor_by_machine: dict[int, datetime | None] = {}
    for mid in eligible_machine_ids:
        _, planned_end, next_cursor = advance_machine_queue(
            ctx, machine_cursors[mid], calendars[mid], now
        )
        next_cursor_by_machine[mid] = next_cursor
        end = planned_end if planned_end is not None else sentinel
        if end != sentinel:
            all_sentinel = False
        if best_end is None or end < best_end:
            best_end = end
            best_machine_id = mid
            best_next_cursor = next_cursor

    if best_machine_id is None:
        return None

    if all_sentinel:
        queue_lengths = machine_queue_lengths or {}
        least_loaded_id = min(
            eligible_machine_ids, key=lambda mid: (queue_lengths.get(mid, 0), mid)
        )
        return least_loaded_id, next_cursor_by_machine[least_loaded_id]

    return best_machine_id, best_next_cursor


def resolve_best_pool(
    ctx: OrderSchedulingContext,
    eligible_pool_ids: list[int],
    pool_machine_ids: dict[int, list[int]],
    machine_cursors: dict[int, datetime | None],
    calendars: dict[int, MachineCalendar],
    now: datetime,
    pool_queue_lengths: dict[int, int] | None = None,
) -> tuple[int, int, datetime | None] | None:
    """Pool analog of resolve_best_machine: the pool whose earliest-finishing
    member finishes the candidate soonest. Returns (pool_id, member_id,
    next_cursor), or None without a timeable member. The member is never
    persisted; it only tells the caller whose cursor to advance. When all
    trials are undated, the pool with the shortest queue wins.
    """
    best_pool_id: int | None = None
    best_member_id: int | None = None
    best_end: datetime | None = None
    best_next_cursor: datetime | None = None
    sentinel = datetime.max.replace(tzinfo=UTC)
    all_sentinel = True
    trial_by_pool: dict[int, tuple[int, datetime | None]] = {}

    for pool_id in eligible_pool_ids:
        trial = _best_pool_member_trial(
            ctx, pool_machine_ids.get(pool_id, []), machine_cursors, calendars, now, sentinel
        )
        if trial is None:
            continue
        pool_best_member, pool_best_end, pool_best_next_cursor = trial
        trial_by_pool[pool_id] = (pool_best_member, pool_best_next_cursor)
        if pool_best_end != sentinel:
            all_sentinel = False
        if best_end is None or pool_best_end < best_end:
            best_end = pool_best_end
            best_pool_id = pool_id
            best_member_id = pool_best_member
            best_next_cursor = pool_best_next_cursor

    if best_pool_id is None or best_member_id is None:
        return None

    if all_sentinel:
        queue_lengths = pool_queue_lengths or {}
        least_loaded_pool_id = min(trial_by_pool, key=lambda pid: (queue_lengths.get(pid, 0), pid))
        member_id, next_cursor = trial_by_pool[least_loaded_pool_id]
        return least_loaded_pool_id, member_id, next_cursor

    return best_pool_id, best_member_id, best_next_cursor


def _best_pool_member_trial(
    ctx: OrderSchedulingContext,
    member_ids: list[int],
    machine_cursors: dict[int, datetime | None],
    calendars: dict[int, MachineCalendar],
    now: datetime,
    sentinel: datetime,
) -> tuple[int, datetime, datetime | None] | None:
    """The earliest-finishing member of one pool as (member_id, end,
    next_cursor), with `end` set to the sentinel for an undated trial.
    Members outside this run's calendars are skipped."""
    pool_best_member: int | None = None
    pool_best_end: datetime | None = None
    pool_best_next_cursor: datetime | None = None
    for member_id in member_ids:
        if member_id not in calendars:
            continue
        _, planned_end, next_cursor = advance_machine_queue(
            ctx, machine_cursors.get(member_id), calendars[member_id], now
        )
        end = planned_end if planned_end is not None else sentinel
        if pool_best_end is None or end < pool_best_end:
            pool_best_end = end
            pool_best_member = member_id
            pool_best_next_cursor = next_cursor
    if pool_best_member is None or pool_best_end is None:
        return None
    return pool_best_member, pool_best_end, pool_best_next_cursor


def resolve_least_loaded_machine(
    ctx: OrderSchedulingContext,
    eligible_machine_ids: list[int],
    machine_cursors: dict[int, datetime | None],
    machine_booked_minutes: dict[int, int],
    calendars: dict[int, MachineCalendar],
    now: datetime,
) -> tuple[int, datetime | None] | None:
    """BALANCED_LOAD's machine choice: the eligible machine with the fewest
    booked minutes, ties broken by id."""
    if not eligible_machine_ids:
        return None
    best_machine_id = min(
        eligible_machine_ids, key=lambda mid: (machine_booked_minutes.get(mid, 0), mid)
    )
    _, _, next_cursor = advance_machine_queue(
        ctx, machine_cursors[best_machine_id], calendars[best_machine_id], now
    )
    return best_machine_id, next_cursor


def resolve_least_loaded_pool(
    ctx: OrderSchedulingContext,
    eligible_pool_ids: list[int],
    pool_machine_ids: dict[int, list[int]],
    machine_cursors: dict[int, datetime | None],
    machine_booked_minutes: dict[int, int],
    calendars: dict[int, MachineCalendar],
    now: datetime,
) -> tuple[int, int, datetime | None] | None:
    """BALANCED_LOAD's pool choice: the pool with the fewest booked minutes
    summed over its members, ties broken by id. Within the winning pool the
    earliest-finishing member supplies the slot."""
    sentinel = datetime.max.replace(tzinfo=UTC)
    scored = sorted(
        (sum(machine_booked_minutes.get(mid, 0) for mid in pool_machine_ids.get(pid, [])), pid)
        for pid in eligible_pool_ids
    )
    for _, pool_id in scored:
        trial = _best_pool_member_trial(
            ctx, pool_machine_ids.get(pool_id, []), machine_cursors, calendars, now, sentinel
        )
        if trial is not None:
            member_id, _, next_cursor = trial
            return pool_id, member_id, next_cursor
    return None


def resolve_machine_for_candidate(
    strategy: str,
    ctx: OrderSchedulingContext,
    eligible_machine_ids: list[int],
    machine_cursors: dict[int, datetime | None],
    machine_booked_minutes: dict[int, int],
    calendars: dict[int, MachineCalendar],
    now: datetime,
    machine_queue_lengths: dict[int, int] | None = None,
) -> tuple[int, datetime | None] | None:
    """Dispatches on a SelectionStrategy value, falling back to
    EARLIEST_FINISH for unknown values."""
    if strategy == SelectionStrategy.LEAST_LOADED.value:
        return resolve_least_loaded_machine(
            ctx, eligible_machine_ids, machine_cursors, machine_booked_minutes, calendars, now
        )
    return resolve_best_machine(
        ctx, eligible_machine_ids, machine_cursors, calendars, now, machine_queue_lengths
    )


def resolve_pool_for_candidate(
    strategy: str,
    ctx: OrderSchedulingContext,
    eligible_pool_ids: list[int],
    pool_machine_ids: dict[int, list[int]],
    machine_cursors: dict[int, datetime | None],
    machine_booked_minutes: dict[int, int],
    calendars: dict[int, MachineCalendar],
    now: datetime,
    pool_queue_lengths: dict[int, int] | None = None,
) -> tuple[int, int, datetime | None] | None:
    """Pool analog of resolve_machine_for_candidate."""
    if strategy == SelectionStrategy.LEAST_LOADED.value:
        return resolve_least_loaded_pool(
            ctx,
            eligible_pool_ids,
            pool_machine_ids,
            machine_cursors,
            machine_booked_minutes,
            calendars,
            now,
        )
    return resolve_best_pool(
        ctx,
        eligible_pool_ids,
        pool_machine_ids,
        machine_cursors,
        calendars,
        now,
        pool_queue_lengths,
    )


_ALGORITHM_STRATEGIES: dict[str, tuple[str, str]] = {
    AutoPlanAlgorithm.URGENT_FIRST.value: (
        OrderingStrategy.PRIORITY_EDD.value,
        SelectionStrategy.EARLIEST_FINISH.value,
    ),
    AutoPlanAlgorithm.STRICT_DEADLINE.value: (
        OrderingStrategy.EDD.value,
        SelectionStrategy.EARLIEST_FINISH.value,
    ),
    AutoPlanAlgorithm.FAIR_QUEUE.value: (
        OrderingStrategy.FIFO.value,
        SelectionStrategy.EARLIEST_FINISH.value,
    ),
    AutoPlanAlgorithm.BALANCED_LOAD.value: (
        OrderingStrategy.PRIORITY_EDD.value,
        SelectionStrategy.LEAST_LOADED.value,
    ),
    AutoPlanAlgorithm.CRITICAL_RATIO.value: (
        OrderingStrategy.CRITICAL_RATIO.value,
        SelectionStrategy.EARLIEST_FINISH.value,
    ),
    AutoPlanAlgorithm.SHORTEST_PROCESSING_TIME.value: (
        OrderingStrategy.SPT.value,
        SelectionStrategy.EARLIEST_FINISH.value,
    ),
}


def resolve_algorithm_strategies(algorithm: str) -> tuple[str, str]:
    """Maps an AutoPlanAlgorithm value to (ordering, selection) strategies,
    falling back to the default algorithm for unknown values."""
    return _ALGORITHM_STRATEGIES.get(
        algorithm, _ALGORITHM_STRATEGIES[AutoPlanAlgorithm.default().value]
    )
