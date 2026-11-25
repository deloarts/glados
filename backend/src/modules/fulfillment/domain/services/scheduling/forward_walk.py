"""The forward walk that dates every production order on its queue.

The walk places each machine's orders in queue_sequence order, each
starting at max(previous planned_end, earliest_start), never before now for
a queued order, and snapped into working windows. A manual order without a
machine shares no queue: it is placed on its own against the admin default
calendar, so manual orders take no capacity from each other. Running orders anchor at
their latest start, and pinned and frozen orders keep their window without
moving the cursor backwards; a kept window that overlaps the order before it
is flagged. A machine whose calendar holds no working time leaves its own
queue undated and flagged, and every other queue is walked as usual.
earliest_start folds in not_before, the lot's predecessor chain readiness
and, for sequence 1, raw-material readiness. An order whose predecessor
chain has an undated open position, or whose sequence-1 raw material has
neither arrived nor a forecast, stays undated rather than being floored at
a meaningless cursor, unless parts are already waiting at its step. Every
day the walk floors at or compares with is a day of the tenant's timezone,
which each context carries as `zone`: an earliest start day begins at local
midnight, and a planned end counts on its local day against the target date.

One schedule_all pass reads predecessor readiness from data fixed before
the walk, so a chain of dependent positions can lag behind.
schedule_all_propagated repeats the pass, refreshing readiness from the
previous pass's placed ends, until nothing changes. Each pass settles at
least one more link of every chain, so an acyclic set of chains settles
within one pass per position plus the pass that finds nothing changed;
that count is the pass limit. Orders still changing at the limit wait on
a cycle, such as a successor queued ahead of its own predecessor on one
machine, which no number of passes resolves; the result names them in
unsettled_order_ids.

explain_earliest_start reuses the walk's own branches so the explanation
shown to users can never disagree with the placement.
"""

from collections.abc import Iterable
from dataclasses import dataclass
from dataclasses import field
from dataclasses import replace
from datetime import date
from datetime import datetime
from datetime import tzinfo
from typing import Literal

from src.modules.fulfillment.domain.errors import NoWorkingTimeError
from src.modules.fulfillment.domain.policies.wait_after import ready_after_wait
from src.modules.fulfillment.domain.services.scheduling._shared import as_day
from src.modules.fulfillment.domain.services.scheduling._shared import day_of
from src.modules.fulfillment.domain.services.scheduling._shared import day_start
from src.modules.fulfillment.domain.services.scheduling.chain_cycles import cycle_blocked_order_ids
from src.modules.fulfillment.domain.services.scheduling.earliest_start import compute_earliest_start
from src.modules.fulfillment.domain.services.scheduling.earliest_start import (
    resolve_internal_predecessor_ready_at,
)
from src.modules.fulfillment.domain.services.scheduling.machine_calendar import MachineCalendar
from src.modules.fulfillment.domain.services.scheduling.machine_calendar import place
from src.modules.fulfillment.domain.services.scheduling.walk_context import ExternalForecast
from src.modules.fulfillment.domain.services.scheduling.walk_context import OrderSchedulingContext
from src.modules.fulfillment.domain.services.scheduling.walk_context import ScheduledOrder
from src.modules.fulfillment.domain.services.scheduling.walk_context import (
    refresh_predecessor_readiness,
)
from src.modules.fulfillment.domain.services.scheduling.walk_context import (
    resolve_external_forecasts,
)
from src.modules.fulfillment.domain.value_objects.production_status import (
    TERMINAL_PRODUCTION_ORDER_STATUSES,
)
from src.modules.fulfillment.domain.value_objects.production_status import ProductionOrderStatus
from src.modules.fulfillment.domain.value_objects.schedule_conflict import ScheduleConflictReason
from src.shared_kernel.domain.services.clock import as_utc


def _static_conflicts(ctx: OrderSchedulingContext) -> list[str]:
    conflicts: list[str] = []
    if ctx.capability_mismatch:
        conflicts.append(ScheduleConflictReason.CAPABILITY_MISMATCH.value)
    if ctx.uncategorized_step:
        conflicts.append(ScheduleConflictReason.UNCATEGORIZED_STEP.value)
    if ctx.position_not_fully_queued:
        conflicts.append(ScheduleConflictReason.POSITION_NOT_FULLY_QUEUED.value)
    if ctx.time_estimate_source == "missing":
        conflicts.append(ScheduleConflictReason.MISSING_TIME_ESTIMATE.value)
    elif ctx.time_estimate_source == "budget":
        conflicts.append(ScheduleConflictReason.ESTIMATE_FROM_TIME_BUDGET.value)
    # Terminal orders have nothing left to block and are never flagged.
    if ctx.stale_external_predecessor and ctx.status not in TERMINAL_PRODUCTION_ORDER_STATUSES:
        conflicts.append(ScheduleConflictReason.EXTERNAL_DATE_BEFORE_PREDECESSOR.value)
    if ctx.machine_down and ctx.status not in TERMINAL_PRODUCTION_ORDER_STATUSES:
        conflicts.append(ScheduleConflictReason.MACHINE_DOWN.value)
    # Flagged here so it also reaches schedule_unassigned_orders.
    if (
        not ctx.upstream_input_available
        and ctx.position_sequence > 1
        and ctx.status not in TERMINAL_PRODUCTION_ORDER_STATUSES
    ):
        conflicts.append(ScheduleConflictReason.WAITING_ON_PREDECESSOR.value)
    # Sequence 1's upstream is raw material, so it gets its own badge.
    elif (
        not ctx.upstream_input_available
        and ctx.position_sequence <= 1
        and ctx.status not in TERMINAL_PRODUCTION_ORDER_STATUSES
    ):
        conflicts.append(ScheduleConflictReason.WAITING_ON_MATERIAL.value)
    return conflicts


def _with_waiting_and_target_flags(
    conflicts: list[str],
    ctx: OrderSchedulingContext,
    planned_end: datetime | None,
    now: datetime,
) -> list[str]:
    """Adds the flags that compare a day: waiting while the predecessor's
    ready day lies after today, and past the target date while the pieces
    are ready on a later day, the planned end plus the wait after the
    order's position. Both days are the tenant's, so in Vienna an order
    ending at 23:30 UTC on its target date ends on the next local day and
    is late."""
    result = list(conflicts)
    # _static_conflicts may already have flagged the same blockage.
    if (
        ctx.predecessor_ready_at is not None
        and ctx.predecessor_ready_at > day_of(now, ctx.zone)
        and ScheduleConflictReason.WAITING_ON_PREDECESSOR.value not in result
    ):
        result.append(ScheduleConflictReason.WAITING_ON_PREDECESSOR.value)
    if (
        ctx.target_date is not None
        and planned_end is not None
        and day_of(ready_after_wait(planned_end, ctx.wait_after_minutes), ctx.zone)
        > ctx.target_date
    ):
        result.append(ScheduleConflictReason.PAST_TARGET_DATE.value)
    return result


def compute_order_conflicts(
    ctx: OrderSchedulingContext, planned_end: datetime | None, now: datetime
) -> list[str]:
    """Conflict flags from an order's persisted state without a calendar
    walk, for the plain production-order read model. Never includes
    NO_MACHINE_ASSIGNED; callers add that based on machine_id."""
    return _with_waiting_and_target_flags(_static_conflicts(ctx), ctx, planned_end, now)


def is_unplannable_for_missing_material(ctx: OrderSchedulingContext) -> bool:
    """True for a non-terminal sequence-1 order whose raw material has
    neither arrived nor a delivery forecast. The walk leaves it undated and
    Auto-Plan skips it with a reported reason."""
    return (
        ctx.position_sequence <= 1
        and not ctx.upstream_input_available
        and ctx.material_ready_at is None
        and ctx.status not in TERMINAL_PRODUCTION_ORDER_STATUSES
    )


EarliestStartReason = Literal[
    "in_progress",
    "pinned",
    "frozen",
    "not_before",
    "predecessor",
    "material",
    "queue",
    "unknown_chain",
    "missing_material",
    "none",
]


@dataclass(frozen=True)
class EarliestStartExplanation:
    """What currently governs one order's earliest possible start, derived
    on read. `date` is None for unknown_chain, missing_material and none."""

    reason: EarliestStartReason
    date: date | None


def _is_running(ctx: OrderSchedulingContext) -> bool:
    return ctx.status == ProductionOrderStatus.IN_PROGRESS and ctx.actual_start is not None


def _running_since(ctx: OrderSchedulingContext) -> datetime | None:
    """When a started order last began running: the later of its first start
    and its latest resume. None before the first start."""
    if ctx.actual_start is None:
        return None
    if ctx.last_resumed_at is None:
        return as_utc(ctx.actual_start)
    return max(as_utc(ctx.actual_start), as_utc(ctx.last_resumed_at))


def explain_earliest_start(
    ctx: OrderSchedulingContext, *, on_queue: bool = True
) -> EarliestStartExplanation:
    """Names the advance_machine_queue branch that governs ctx's earliest
    start, so a read model can never disagree with the forward walk.

    The reason is the latest of not_before, predecessor and material
    readiness, except that `queue` is reported when the persisted
    planned_start lies later than that date, because the machine queue
    pushed the start out. The date reported then stays the constraint's.
    A manual order without a machine waits behind no other order, so the
    caller passes `on_queue=False` for it and `queue` is never reported.
    Every date is a day of the tenant's timezone."""
    running_since = _running_since(ctx)
    if running_since is not None:
        return EarliestStartExplanation("in_progress", day_of(running_since, ctx.zone))
    if (
        (ctx.pinned or ctx.frozen)
        and ctx.existing_planned_start is not None
        and ctx.existing_planned_end is not None
    ):
        return EarliestStartExplanation(
            "pinned" if ctx.pinned else "frozen", day_of(ctx.existing_planned_start, ctx.zone)
        )
    if (
        ctx.predecessor_chain_unknown
        and not ctx.upstream_input_available
        and ctx.position_sequence > 1
    ):
        return EarliestStartExplanation("unknown_chain", None)
    if is_unplannable_for_missing_material(ctx):
        return EarliestStartExplanation("missing_material", None)

    not_before, predecessor_ready_at, earliest_start_date = _earliest_start_days(ctx)
    if earliest_start_date is None:
        return EarliestStartExplanation("none", None)
    if (
        on_queue
        and ctx.existing_planned_start is not None
        and day_of(ctx.existing_planned_start, ctx.zone) > earliest_start_date
    ):
        return EarliestStartExplanation("queue", earliest_start_date)
    if not_before == earliest_start_date:
        return EarliestStartExplanation("not_before", earliest_start_date)
    if predecessor_ready_at == earliest_start_date:
        return EarliestStartExplanation("predecessor", earliest_start_date)
    return EarliestStartExplanation("material", earliest_start_date)


def _earliest_start_days(
    ctx: OrderSchedulingContext,
) -> tuple[date | None, date | None, date | None]:
    """The not_before and predecessor days and the earliest start day of
    ctx, each a day of the tenant's timezone. A moment that reached a date
    field, such as an actual delivery as material readiness, is reduced to
    its day there before the days are compared."""
    not_before = as_day(ctx.not_before, ctx.zone)
    predecessor_ready_at = as_day(ctx.predecessor_ready_at, ctx.zone)
    material_ready_at = as_day(ctx.material_ready_at, ctx.zone)
    return (
        not_before,
        predecessor_ready_at,
        compute_earliest_start(not_before, predecessor_ready_at, material_ready_at),
    )


@dataclass(frozen=True)
class QueuePlacement:
    """One order placed on its queue: the window, the cursor for the next
    order, and why the placement is flagged. `no_working_time` says the
    calendar holds no working time for the order; `overlap` says a pinned
    or frozen window starts before the previous order ends, and
    `before_predecessor` that it starts before its predecessor is ready."""

    planned_start: datetime | None
    planned_end: datetime | None
    next_cursor: datetime | None
    no_working_time: bool = False
    overlap: bool = False
    before_predecessor: bool = False


def advance_machine_queue(
    ctx: OrderSchedulingContext,
    cursor: datetime | None,
    calendar: MachineCalendar,
    now: datetime,
) -> tuple[datetime | None, datetime | None, datetime | None]:
    """Places one order against an already-known cursor and returns
    (planned_start, planned_end, next_cursor), see place_on_queue. Auto-Plan
    appends to queues only, so the cursor is the same for every trial at a
    given point and trials need not re-walk the queue."""
    placement = place_on_queue(ctx, cursor, calendar, now)
    return placement.planned_start, placement.planned_end, placement.next_cursor


def place_on_queue(
    ctx: OrderSchedulingContext,
    cursor: datetime | None,
    calendar: MachineCalendar,
    now: datetime,
) -> QueuePlacement:
    """Places one order against an already-known cursor.

    PAUSED orders consume no capacity. A running order anchors at its
    latest start or resume, which may lie in the past, and a pinned or
    frozen order keeps its window, and so does a running order its anchor;
    neither moves the cursor backwards, and one that starts before the
    cursor is flagged as an overlap. An order whose predecessor chain is unknown (with nothing
    waiting at its step), or a sequence-1 order with neither raw material
    nor a delivery forecast, stays undated, because a date floored at the
    cursor would be fiction. A queued order is placed at the latest of the
    cursor, its earliest start and now, so a readiness date in the past
    never plans it in the past. An earliest start day begins at the
    tenant's local midnight. A calendar without working time leaves the
    order undated and flagged.
    """
    if ctx.status == ProductionOrderStatus.PAUSED:
        return QueuePlacement(None, None, cursor)

    running_since = _running_since(ctx)
    if ctx.status == ProductionOrderStatus.IN_PROGRESS and running_since is not None:
        try:
            planned_start, planned_end = place(
                running_since, ctx.estimated_duration_minutes, calendar
            )
        except NoWorkingTimeError:
            return QueuePlacement(None, None, cursor, no_working_time=True)
        if cursor is None:
            return QueuePlacement(planned_start, planned_end, planned_end)
        cursor = as_utc(cursor)
        return QueuePlacement(
            planned_start, planned_end, max(cursor, planned_end), overlap=planned_start < cursor
        )

    if (
        (ctx.pinned or ctx.frozen)
        and ctx.existing_planned_start is not None
        and ctx.existing_planned_end is not None
    ):
        pinned_start = as_utc(ctx.existing_planned_start)
        pinned_end = as_utc(ctx.existing_planned_end)
        ready = _predecessor_ready(ctx)
        early = ready is not None and pinned_start < ready
        if cursor is None:
            return QueuePlacement(pinned_start, pinned_end, pinned_end, before_predecessor=early)
        cursor = as_utc(cursor)
        return QueuePlacement(
            pinned_start,
            pinned_end,
            max(cursor, pinned_end),
            overlap=pinned_start < cursor,
            before_predecessor=early,
        )

    if (
        ctx.predecessor_chain_unknown
        and not ctx.upstream_input_available
        and ctx.position_sequence > 1
    ):
        return QueuePlacement(None, None, cursor)

    if is_unplannable_for_missing_material(ctx):
        return QueuePlacement(None, None, cursor)

    _not_before, _predecessor_ready_at, earliest_start_date = _earliest_start_days(ctx)
    earliest = day_start(earliest_start_date, ctx.zone) if earliest_start_date else as_utc(now)
    if ctx.predecessor_ready_moment is not None:
        earliest = max(earliest, as_utc(ctx.predecessor_ready_moment))
    if ctx.status == ProductionOrderStatus.QUEUED:
        earliest = max(earliest, as_utc(now))
    floor = max(as_utc(cursor), earliest) if cursor is not None else earliest
    try:
        planned_start, planned_end = place(floor, ctx.estimated_duration_minutes, calendar)
    except NoWorkingTimeError:
        return QueuePlacement(None, None, cursor, no_working_time=True)
    return QueuePlacement(planned_start, planned_end, planned_end)


def _predecessor_ready(ctx: OrderSchedulingContext) -> datetime | None:
    """The moment the previous step's pieces are ready, the same floor a
    queued order is placed at: the predecessor's planned end, or the start
    of its ready day, at the tenant's local midnight, when only a day is
    known."""
    if ctx.predecessor_ready_moment is not None:
        return as_utc(ctx.predecessor_ready_moment)
    if ctx.predecessor_ready_at is not None:
        return day_start(ctx.predecessor_ready_at, ctx.zone)
    return None


def _placement_conflicts(placement: QueuePlacement) -> list[str]:
    conflicts: list[str] = []
    if placement.no_working_time:
        conflicts.append(ScheduleConflictReason.NO_WORKING_TIME.value)
    if placement.overlap:
        conflicts.append(ScheduleConflictReason.WINDOW_OVERLAP.value)
    if placement.before_predecessor:
        conflicts.append(ScheduleConflictReason.WINDOW_BEFORE_PREDECESSOR.value)
    return conflicts


def _walk_machine_queue(
    orders: list[OrderSchedulingContext],
    calendar: MachineCalendar,
    now: datetime,
) -> tuple[list[ScheduledOrder], datetime | None]:
    """Walks one machine's non-terminal orders and returns the placements
    plus the final cursor. Running orders come first, since the machine is
    busy with them now wherever they sit in the queue (a pool start appends
    the started order, and an operator may start one that is not at the
    head); the others follow in queue order. order_id breaks ties, so the
    walk never depends on fetch order."""
    results: list[ScheduledOrder] = []
    cursor: datetime | None = None

    for ctx in sorted(orders, key=lambda o: (not _is_running(o), o.queue_sequence, o.order_id)):
        static_conflicts = _static_conflicts(ctx)
        placement = place_on_queue(ctx, cursor, calendar, now)
        cursor = placement.next_cursor
        conflicts = _with_waiting_and_target_flags(
            static_conflicts, ctx, placement.planned_end, now
        )
        conflicts += _placement_conflicts(placement)
        results.append(
            ScheduledOrder(ctx.order_id, placement.planned_start, placement.planned_end, conflicts)
        )

    return results, cursor


def _walk_manual_orders(
    orders: list[OrderSchedulingContext],
    calendar: MachineCalendar,
    now: datetime,
) -> list[ScheduledOrder]:
    """Places every manual order without a machine on its own against the
    admin default calendar. There is no shared cursor, so one order never
    waits for another and queue_sequence changes no date: each starts at
    the latest of its earliest start, its predecessor's ready moment and
    now. Running, pinned and frozen orders keep their anchor or window as
    on a machine queue, without an overlap to flag."""
    results: list[ScheduledOrder] = []
    for ctx in sorted(orders, key=lambda o: o.order_id):
        placement = place_on_queue(ctx, None, calendar, now)
        conflicts = _with_waiting_and_target_flags(
            _static_conflicts(ctx), ctx, placement.planned_end, now
        )
        conflicts += _placement_conflicts(placement)
        results.append(
            ScheduledOrder(ctx.order_id, placement.planned_start, placement.planned_end, conflicts)
        )
    return results


def schedule_unassigned_orders(orders: list[OrderSchedulingContext]) -> list[ScheduledOrder]:
    """Orders without a machine get no dates and are flagged
    NO_MACHINE_ASSIGNED, except pool-assigned ones (for example a pool
    emptied since assignment), which reflect a deliberate planner decision."""
    results = []
    for ctx in orders:
        conflicts = _static_conflicts(ctx)
        if ctx.machine_pool_id is None:
            conflicts.append(ScheduleConflictReason.NO_MACHINE_ASSIGNED.value)
        results.append(ScheduledOrder(ctx.order_id, None, None, conflicts))
    return results


def _best_member_placement(
    ctx: OrderSchedulingContext,
    member_calendars: dict[int, MachineCalendar],
    cursors: dict[int, datetime | None],
    now: datetime,
) -> tuple[int | None, QueuePlacement | None]:
    """Trials ctx on every pool member and returns the one that finishes
    earliest with its placement, or None for an empty pool. Calendar-
    independent results tie and the first member wins, which is harmless
    because they consume no capacity. An undated placement says no working
    time only when no member has any for the order."""
    best_member_id: int | None = None
    best: QueuePlacement | None = None
    every_member_idle = True

    for member_id, calendar in member_calendars.items():
        placement = place_on_queue(ctx, cursors[member_id], calendar, now)
        every_member_idle = every_member_idle and placement.no_working_time
        if best is None or (
            placement.planned_end is not None
            and (best.planned_end is None or placement.planned_end < best.planned_end)
        ):
            best_member_id, best = member_id, placement

    if best is not None and best.planned_end is None:
        best = replace(best, no_working_time=every_member_idle)
    return best_member_id, best


@dataclass(frozen=True)
class ScheduleWalkResult:
    """The output of one schedule_all walk. machine_cursors holds each
    machine's last committed planned_end, including pool orders that
    floated onto it."""

    by_machine: dict[int, list[ScheduledOrder]]
    by_pool: dict[int, list[ScheduledOrder]]
    manual: list[ScheduledOrder]
    unassigned: list[ScheduledOrder]
    machine_cursors: dict[int, datetime | None]
    # Keyed by lot_position_id; only schedule_all_propagated fills it.
    external_forecasts: dict[int, ExternalForecast] = field(default_factory=dict)
    # The orders whose readiness still changed at schedule_all_propagated's
    # pass limit, empty once the walk settled (module docstring).
    unsettled_order_ids: frozenset[int] = frozenset()

    def all_orders(self) -> list[ScheduledOrder]:
        """Every placement of the walk, flattened in no meaningful order."""
        result: list[ScheduledOrder] = []
        for orders in self.by_machine.values():
            result.extend(orders)
        for orders in self.by_pool.values():
            result.extend(orders)
        result.extend(self.manual)
        result.extend(self.unassigned)
        return result


# (ctx, winning_member_id, placement) for one pool's queue head in
# schedule_all's merge.
_PoolTrial = tuple[OrderSchedulingContext, int, QueuePlacement]


def schedule_all(
    machine_queues: dict[int, list[OrderSchedulingContext]],
    machine_calendars: dict[int, MachineCalendar],
    pool_queues: dict[int, list[OrderSchedulingContext]],
    pool_members: dict[int, list[int]],
    manual_queue: list[OrderSchedulingContext],
    manual_calendar: MachineCalendar,
    unassigned: list[OrderSchedulingContext],
    now: datetime,
) -> ScheduleWalkResult:
    """The unified forward walk over machine, pool, manual and unassigned
    queues. All of them share one machine_cursors map, so a pool order can
    never land on a member's own commitments and two pools sharing a member
    can never double-book it.

    Machine-assigned queues are walked first and win outright. Pools are
    then merged as an earliest-finish merge of FIFO queues: each round
    trials every pool's head, commits all undated heads at once (so one
    undated head cannot stall another pool), and otherwise commits only the
    single earliest finish, ties broken by pool id then member id. Each
    manual order is placed on its own against the admin default calendar
    (_walk_manual_orders), and unassigned orders get no dates.
    """
    _assert_machine_queues_have_calendars(machine_queues, machine_calendars)
    by_machine, machine_cursors = _walk_all_machine_queues(machine_queues, machine_calendars, now)
    by_pool, pool_member_calendars, pool_sorted_orders, pool_heads = _seed_pool_walk_state(
        pool_queues, pool_members, machine_calendars
    )
    _merge_pool_queues(
        by_pool, pool_member_calendars, pool_sorted_orders, pool_heads, machine_cursors, now
    )

    manual = _walk_manual_orders(manual_queue, manual_calendar, now)
    unassigned_results = schedule_unassigned_orders(unassigned)

    return ScheduleWalkResult(
        by_machine=by_machine,
        by_pool=by_pool,
        manual=manual,
        unassigned=unassigned_results,
        machine_cursors=machine_cursors,
    )


def _assert_machine_queues_have_calendars(
    machine_queues: dict[int, list[OrderSchedulingContext]],
    machine_calendars: dict[int, MachineCalendar],
) -> None:
    """A queue without a calendar is a caller bug; raising beats silently
    dropping the queue."""
    for machine_id in machine_queues:
        if machine_id not in machine_calendars:
            raise ValueError(f"machine {machine_id} has orders queued but no calendar")


def _walk_all_machine_queues(
    machine_queues: dict[int, list[OrderSchedulingContext]],
    machine_calendars: dict[int, MachineCalendar],
    now: datetime,
) -> tuple[dict[int, list[ScheduledOrder]], dict[int, datetime | None]]:
    """Walks every machine queue. Every machine with a calendar gets a
    cursor entry, even with an empty queue, so the pool merge can seed
    from it."""
    by_machine: dict[int, list[ScheduledOrder]] = {}
    machine_cursors: dict[int, datetime | None] = {}
    for machine_id in sorted(machine_calendars):
        results, cursor = _walk_machine_queue(
            machine_queues.get(machine_id, []), machine_calendars[machine_id], now
        )
        by_machine[machine_id] = results
        machine_cursors[machine_id] = cursor
    return by_machine, machine_cursors


def _seed_pool_walk_state(
    pool_queues: dict[int, list[OrderSchedulingContext]],
    pool_members: dict[int, list[int]],
    machine_calendars: dict[int, MachineCalendar],
) -> tuple[
    dict[int, list[ScheduledOrder]],
    dict[int, dict[int, MachineCalendar]],
    dict[int, list[OrderSchedulingContext]],
    dict[int, int],
]:
    """Seeds the state _merge_pool_queues consumes. A pool with no member
    that has a calendar is resolved immediately as unassigned."""
    by_pool: dict[int, list[ScheduledOrder]] = {}
    pool_member_calendars: dict[int, dict[int, MachineCalendar]] = {}
    pool_sorted_orders: dict[int, list[OrderSchedulingContext]] = {}
    pool_heads: dict[int, int] = {}

    for pool_id, orders in pool_queues.items():
        members = [mid for mid in pool_members.get(pool_id, []) if mid in machine_calendars]
        if not members:
            by_pool[pool_id] = schedule_unassigned_orders(orders)
            continue
        by_pool[pool_id] = []
        pool_member_calendars[pool_id] = {mid: machine_calendars[mid] for mid in members}
        pool_sorted_orders[pool_id] = sorted(orders, key=lambda o: (o.queue_sequence, o.order_id))
        pool_heads[pool_id] = 0

    return by_pool, pool_member_calendars, pool_sorted_orders, pool_heads


def _merge_pool_queues(
    by_pool: dict[int, list[ScheduledOrder]],
    pool_member_calendars: dict[int, dict[int, MachineCalendar]],
    pool_sorted_orders: dict[int, list[OrderSchedulingContext]],
    pool_heads: dict[int, int],
    machine_cursors: dict[int, datetime | None],
    now: datetime,
) -> None:
    """Earliest-finish merge of the pool queues (see schedule_all),
    mutating by_pool, machine_cursors and pool_heads in place. The winning
    member is reported only as trial_machine_id and the order's machine_id
    stays unset, because the concrete machine is chosen later by Auto-Plan
    or the shop-floor Start dialog."""

    def _remaining_pool_ids() -> list[int]:
        return [pid for pid in pool_sorted_orders if pool_heads[pid] < len(pool_sorted_orders[pid])]

    while _remaining_pool_ids():
        trials: dict[int, _PoolTrial] = {}
        for pool_id in _remaining_pool_ids():
            ctx = pool_sorted_orders[pool_id][pool_heads[pool_id]]
            member_id, placement = _best_member_placement(
                ctx, pool_member_calendars[pool_id], machine_cursors, now
            )
            assert member_id is not None and placement is not None
            trials[pool_id] = (ctx, member_id, placement)

        dateless_pool_ids = [
            pid for pid, (_, _, placement) in trials.items() if placement.planned_end is None
        ]
        if dateless_pool_ids:
            for pool_id in dateless_pool_ids:
                ctx, _member_id, placement = trials[pool_id]
                static_conflicts = _static_conflicts(ctx)
                conflicts = _with_waiting_and_target_flags(static_conflicts, ctx, None, now)
                conflicts += _placement_conflicts(placement)
                by_pool[pool_id].append(ScheduledOrder(ctx.order_id, None, None, conflicts, None))
                pool_heads[pool_id] += 1
            continue

        best_pool_id = min(trials, key=lambda pid: _finish_order(pid, trials[pid]))
        ctx, member_id, placement = trials[best_pool_id]
        static_conflicts = _static_conflicts(ctx)
        conflicts = _with_waiting_and_target_flags(
            static_conflicts, ctx, placement.planned_end, now
        )
        conflicts += _placement_conflicts(placement)
        by_pool[best_pool_id].append(
            ScheduledOrder(
                ctx.order_id, placement.planned_start, placement.planned_end, conflicts, member_id
            )
        )
        machine_cursors[member_id] = placement.next_cursor
        pool_heads[best_pool_id] += 1


def _finish_order(pool_id: int, trial: _PoolTrial) -> tuple[datetime, int, int]:
    """The merge's order of dated trials: earliest finish, then pool id,
    then member id."""
    _ctx, member_id, placement = trial
    assert placement.planned_end is not None
    return placement.planned_end, pool_id, member_id


def placed_ends_by_position(
    contexts: Iterable[OrderSchedulingContext], result: ScheduleWalkResult
) -> dict[int, date | None]:
    """Each position's in-run ready date from one pass, the tenant day of
    its latest planned end plus the wait after the position. A position
    whose orders are all undated maps to None rather than being absent, and
    callers must tell the two apart (see position_ready_at_in_run)."""
    scheduled_by_id = {s.order_id: s for s in result.all_orders()}
    ends_by_position: dict[int, list[datetime | None]] = {}
    zone_by_position: dict[int, tzinfo] = {}
    for ctx in contexts:
        if ctx.lot_position_id is None:
            continue
        scheduled = scheduled_by_id.get(ctx.order_id)
        planned_end = scheduled.planned_end if scheduled is not None else None
        ready = (
            ready_after_wait(planned_end, ctx.wait_after_minutes)
            if planned_end is not None
            else None
        )
        ends_by_position.setdefault(ctx.lot_position_id, []).append(ready)
        zone_by_position[ctx.lot_position_id] = ctx.zone
    return {
        position_id: resolve_internal_predecessor_ready_at(ends, zone=zone_by_position[position_id])
        for position_id, ends in ends_by_position.items()
    }


def placed_end_moments_by_position(
    contexts: Iterable[OrderSchedulingContext], result: ScheduleWalkResult
) -> dict[int, datetime | None]:
    """Each position's latest planned end in one pass as a moment, plus the
    wait after the position, the floor of its successors
    (predecessor_ready_moment). A position whose orders are all undated maps
    to None, as in placed_ends_by_position."""
    scheduled_by_id = {s.order_id: s for s in result.all_orders()}
    ends: dict[int, datetime | None] = {}
    for ctx in contexts:
        if ctx.lot_position_id is None:
            continue
        scheduled = scheduled_by_id.get(ctx.order_id)
        end = (
            ready_after_wait(scheduled.planned_end, ctx.wait_after_minutes)
            if scheduled is not None and scheduled.planned_end is not None
            else None
        )
        known = ends.get(ctx.lot_position_id)
        if end is not None:
            ends[ctx.lot_position_id] = max(known, as_utc(end)) if known else as_utc(end)
        else:
            ends.setdefault(ctx.lot_position_id, known)
    return ends


def _all_propagated_contexts(
    machine_queues: dict[int, list[OrderSchedulingContext]],
    pool_queues: dict[int, list[OrderSchedulingContext]],
    manual_queue: list[OrderSchedulingContext],
    unassigned: list[OrderSchedulingContext],
) -> list[OrderSchedulingContext]:
    contexts: list[OrderSchedulingContext] = []
    for queue in machine_queues.values():
        contexts.extend(queue)
    for queue in pool_queues.values():
        contexts.extend(queue)
    contexts.extend(manual_queue)
    contexts.extend(unassigned)
    return contexts


def _refresh_queue(
    queue: list[OrderSchedulingContext],
    placed_end_by_position: dict[int, date | None],
    changed: set[int],
    placed_moment_by_position: dict[int, datetime | None] | None = None,
) -> list[OrderSchedulingContext]:
    """Refreshes every context in one queue and adds to `changed` the order
    of every context whose refreshed fields changed, which is the
    convergence signal."""
    refreshed: list[OrderSchedulingContext] = []
    for ctx in queue:
        new_ctx = refresh_predecessor_readiness(
            ctx, placed_end_by_position, placed_moment_by_position
        )
        if (
            new_ctx.predecessor_ready_at != ctx.predecessor_ready_at
            or new_ctx.predecessor_chain_unknown != ctx.predecessor_chain_unknown
            or new_ctx.stale_external_predecessor != ctx.stale_external_predecessor
            or new_ctx.predecessor_ready_moment != ctx.predecessor_ready_moment
        ):
            changed.add(ctx.order_id)
        refreshed.append(new_ctx)
    return refreshed


def _refresh_grouped_queues(
    queues: dict[int, list[OrderSchedulingContext]],
    placed_end_by_position: dict[int, date | None],
    changed: set[int],
    placed_moment_by_position: dict[int, datetime | None] | None = None,
) -> dict[int, list[OrderSchedulingContext]]:
    return {
        key: _refresh_queue(queue, placed_end_by_position, changed, placed_moment_by_position)
        for key, queue in queues.items()
    }


def _without(
    queues: dict[int, list[OrderSchedulingContext]], blocked: frozenset[int]
) -> dict[int, list[OrderSchedulingContext]]:
    return {
        key: [ctx for ctx in queue if ctx.order_id not in blocked] for key, queue in queues.items()
    }


def _cycle_placements(
    queue: list[OrderSchedulingContext], blocked: frozenset[int]
) -> list[ScheduledOrder]:
    return [
        ScheduledOrder(
            ctx.order_id,
            None,
            None,
            [*_static_conflicts(ctx), ScheduleConflictReason.CHAIN_CYCLE.value],
        )
        for ctx in queue
        if ctx.order_id in blocked
    ]


def _with_cycle_orders(
    result: ScheduleWalkResult,
    blocked: frozenset[int],
    machine_queues: dict[int, list[OrderSchedulingContext]],
    pool_queues: dict[int, list[OrderSchedulingContext]],
    manual_queue: list[OrderSchedulingContext],
    unassigned: list[OrderSchedulingContext],
) -> ScheduleWalkResult:
    """The result with every cycle-blocked order back in its queue,
    undated, so its stored window is cleared too, in place of the
    placement it got as an order without a queue."""
    by_machine = {key: list(orders) for key, orders in result.by_machine.items()}
    for key, queue in machine_queues.items():
        by_machine.setdefault(key, []).extend(_cycle_placements(queue, blocked))
    by_pool = {key: list(orders) for key, orders in result.by_pool.items()}
    for key, queue in pool_queues.items():
        by_pool.setdefault(key, []).extend(_cycle_placements(queue, blocked))
    return replace(
        result,
        by_machine=by_machine,
        by_pool=by_pool,
        manual=[*result.manual, *_cycle_placements(manual_queue, blocked)],
        unassigned=[
            *(s for s in result.unassigned if s.order_id not in blocked),
            *_cycle_placements(unassigned, blocked),
        ],
    )


def propagation_pass_limit(contexts: Iterable[OrderSchedulingContext]) -> int:
    """One pass per distinct position plus the pass that finds nothing
    changed, the most an acyclic set of chains needs (module docstring)."""
    positions = {ctx.lot_position_id for ctx in contexts if ctx.lot_position_id is not None}
    return len(positions) + 1


def schedule_all_propagated(
    machine_queues: dict[int, list[OrderSchedulingContext]],
    machine_calendars: dict[int, MachineCalendar],
    pool_queues: dict[int, list[OrderSchedulingContext]],
    pool_members: dict[int, list[int]],
    manual_queue: list[OrderSchedulingContext],
    manual_calendar: MachineCalendar,
    unassigned: list[OrderSchedulingContext],
    now: datetime,
    max_passes: int | None = None,
) -> tuple[ScheduleWalkResult, int]:
    """Runs schedule_all until predecessor readiness stops changing, so a
    whole lot chain moves in one recompute. Returns the final result, with
    external forecasts filled and the orders a cycle kept from settling,
    and the number of passes run (at least 1). `max_passes` defaults to
    propagation_pass_limit.

    The orders on a wait cycle, such as a step queued ahead of its own
    predecessor on one machine, are taken out of the walk first
    (chain_cycles.py) and come back undated, flagged `chain_cycle`, so they
    take no capacity and no date runs away. A cycle the graph cannot see,
    one through a pool, whose orders go to whichever member finishes first,
    still keeps its orders moving to the pass limit; with the default limit
    those orders are then walked once more the same way, so their runaway
    dates are never kept. The result still names them in
    `unsettled_order_ids`."""
    args = (
        machine_queues,
        machine_calendars,
        pool_queues,
        pool_members,
        manual_queue,
        manual_calendar,
        unassigned,
        now,
    )
    result, passes = _schedule_all_propagated(*args, max_passes, frozenset())
    if max_passes is not None or not result.unsettled_order_ids:
        return result, passes
    settled, more = _schedule_all_propagated(*args, None, result.unsettled_order_ids)
    return replace(settled, unsettled_order_ids=result.unsettled_order_ids), passes + more


def _schedule_all_propagated(
    machine_queues: dict[int, list[OrderSchedulingContext]],
    machine_calendars: dict[int, MachineCalendar],
    pool_queues: dict[int, list[OrderSchedulingContext]],
    pool_members: dict[int, list[int]],
    manual_queue: list[OrderSchedulingContext],
    manual_calendar: MachineCalendar,
    unassigned: list[OrderSchedulingContext],
    now: datetime,
    max_passes: int | None,
    also_blocked: frozenset[int],
) -> tuple[ScheduleWalkResult, int]:
    every_context = _all_propagated_contexts(machine_queues, pool_queues, manual_queue, unassigned)
    blocked = cycle_blocked_order_ids(machine_queues, every_context) | also_blocked
    if blocked:
        # Walked as orders without a queue, which get no dates, so their
        # positions read as undated and the later steps of their lots wait.
        result, passes = _schedule_all_propagated(
            _without(machine_queues, blocked),
            machine_calendars,
            _without(pool_queues, blocked),
            pool_members,
            [ctx for ctx in manual_queue if ctx.order_id not in blocked],
            manual_calendar,
            [*unassigned, *(ctx for ctx in every_context if ctx.order_id in blocked)],
            now,
            max_passes,
            frozenset(),
        )
        return _with_cycle_orders(
            result, blocked, machine_queues, pool_queues, manual_queue, unassigned
        ), passes
    if max_passes is None:
        max_passes = propagation_pass_limit(
            _all_propagated_contexts(machine_queues, pool_queues, manual_queue, unassigned)
        )
    max_passes = max(max_passes, 1)
    for pass_number in range(1, max_passes + 1):
        result = schedule_all(
            machine_queues,
            machine_calendars,
            pool_queues,
            pool_members,
            manual_queue,
            manual_calendar,
            unassigned,
            now,
        )
        contexts = _all_propagated_contexts(machine_queues, pool_queues, manual_queue, unassigned)
        placed_end_by_position = placed_ends_by_position(contexts, result)
        result = replace(
            result,
            external_forecasts=resolve_external_forecasts(contexts, placed_end_by_position),
        )
        moments = placed_end_moments_by_position(contexts, result)
        changed: set[int] = set()
        machine_queues = _refresh_grouped_queues(
            machine_queues, placed_end_by_position, changed, moments
        )
        pool_queues = _refresh_grouped_queues(pool_queues, placed_end_by_position, changed, moments)
        manual_queue = _refresh_queue(manual_queue, placed_end_by_position, changed, moments)
        unassigned = _refresh_queue(unassigned, placed_end_by_position, changed, moments)

        if not changed:
            return result, pass_number
        if pass_number >= max_passes:
            return replace(result, unsettled_order_ids=frozenset(changed)), pass_number

    raise AssertionError("schedule_all_propagated: loop exited without returning")
