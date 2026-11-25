"""Automatic scheduling: a due-date backward pass scores QUEUED candidates,
a greedy loop places them around fixed anchors, and the result comes back
as a before/after diff. The behavioural rules (anchors, assign_machines,
planning levels, pins, downtimes) are in docs/reference/scheduling.md.

The backward pass estimates a position's lead time roughly, from its
orders' durations or, for EXTERNAL, from the forecast's lead-day resolver;
it is not a second forward walk. execute() runs named phases sharing one
_AutoPlanState, and `now` is sampled once in _seed_anchors.

A run has three parts, like the walk. The reads end their transaction
before the placement, which runs without a lock on copies of the orders
read. The write then locks every queue the run may write and the queued
orders in them, reads the queues again, and writes the placements of every
queue that still holds the orders it held at the read. A placement from or
into a queue that changed is not written and is reported as changed while
planning, in the result and in a progress event after the one that streamed
it as placed, so a start, a pin or a new order that committed meanwhile is never
overwritten and never collides with a planned queue place. A write that
lost a race with another transaction is rolled back and written once more.
"""

import asyncio
import random
from collections.abc import Callable
from copy import copy
from dataclasses import dataclass
from dataclasses import field
from datetime import date
from datetime import datetime
from datetime import tzinfo

from anyio import from_thread
from anyio import to_thread

from src.modules.fulfillment.application.dto.production_schedule_dto import AutoPlanCommand
from src.modules.fulfillment.application.dto.production_schedule_dto import AutoPlanOrderDiff
from src.modules.fulfillment.application.dto.production_schedule_dto import AutoPlanProgress
from src.modules.fulfillment.application.dto.production_schedule_dto import AutoPlanProgressCallback
from src.modules.fulfillment.application.dto.production_schedule_dto import AutoPlanProgressOrder
from src.modules.fulfillment.application.dto.production_schedule_dto import AutoPlanResult
from src.modules.fulfillment.application.dto.production_schedule_dto import AutoPlanSkippedOrder
from src.modules.fulfillment.application.services.planned_window import drop_planned_window
from src.modules.fulfillment.application.services.queue_scope_locks import QueueScope
from src.modules.fulfillment.application.services.queue_scope_locks import queue_scope_key
from src.modules.fulfillment.application.services.scheduling_context import SchedulingPrefetch
from src.modules.fulfillment.application.services.scheduling_context import SchedulingRepos
from src.modules.fulfillment.application.services.scheduling_context import build_contexts
from src.modules.fulfillment.application.services.scheduling_context import build_machine_calendars
from src.modules.fulfillment.application.services.scheduling_context import prefetch_scheduling_data
from src.modules.fulfillment.application.services.scheduling_context import resolve_lot_target_date
from src.modules.fulfillment.application.use_cases.production_schedule.recompute_machine_schedule import (
    RecomputeMachineSchedule,
)
from src.modules.fulfillment.domain.entities.admin_settings.production import (
    AdminProductionSettings,
)
from src.modules.fulfillment.domain.entities.lot_position import LotPosition
from src.modules.fulfillment.domain.entities.machine_pool import MachinePool
from src.modules.fulfillment.domain.entities.order_item import OrderItem
from src.modules.fulfillment.domain.entities.production_lot import ProductionLot
from src.modules.fulfillment.domain.entities.production_machine import ProductionMachine
from src.modules.fulfillment.domain.entities.production_order import ProductionOrder
from src.modules.fulfillment.domain.services.production_order_rules import ProductionOrderRules
from src.modules.fulfillment.domain.services.production_order_rules import (
    position_requires_qa_machine,
)
from src.modules.fulfillment.domain.services.scheduling import AutoPlanCandidate
from src.modules.fulfillment.domain.services.scheduling import MachineCalendar
from src.modules.fulfillment.domain.services.scheduling import OrderSchedulingContext
from src.modules.fulfillment.domain.services.scheduling import advance_machine_queue
from src.modules.fulfillment.domain.services.scheduling import compute_position_due_dates
from src.modules.fulfillment.domain.services.scheduling import is_unplannable_for_missing_material
from src.modules.fulfillment.domain.services.scheduling import position_lead_days
from src.modules.fulfillment.domain.services.scheduling import production_order_touches_date
from src.modules.fulfillment.domain.services.scheduling import resolve_algorithm_strategies
from src.modules.fulfillment.domain.services.scheduling import resolve_eligible_machine_ids
from src.modules.fulfillment.domain.services.scheduling import resolve_eligible_pool_ids
from src.modules.fulfillment.domain.services.scheduling import resolve_machine_for_candidate
from src.modules.fulfillment.domain.services.scheduling import resolve_pool_for_candidate
from src.modules.fulfillment.domain.services.scheduling import resolve_position_lead_days
from src.modules.fulfillment.domain.services.scheduling import sort_candidates
from src.modules.fulfillment.domain.value_objects.auto_plan_skip_reason import AutoPlanSkipReason
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionKind
from src.modules.fulfillment.domain.value_objects.production_status import ProductionOrderStatus
from src.modules.fulfillment.domain.value_objects.production_status import UrgencyClass
from src.modules.fulfillment.ports.outbound.fulfillment_settings_repository import (
    IFulfillmentSettingsRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.machine_calendar_repository import (
    IMachineCalendarRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.machine_downtime_repository import (
    IMachineDowntimeRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.machine_pool_repository import (
    IMachinePoolRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.production_machine_repository import (
    IProductionMachineRepository,
)
from src.modules.platform.application.services.tenant_timezone import tenant_zone
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.exceptions import ConcurrentModificationError
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork
from src.shared_kernel.domain.services.clock import now_utc

_URGENCY_RANK = {u.value: i for i, u in enumerate(UrgencyClass)}

# The pause before the write runs once more after a lost race.
_RETRY_DELAY_SECONDS = (0.05, 0.25)

# What a queue's plan depends on, per order of the queue: its id, status,
# pin and queue place. An order whose entry changes, or one that enters or
# leaves the queue, makes the queue's plan stale.
_QueueEntry = tuple[int, str, bool, int | None, int | None, int]


def _never_retry(_exc: BaseException) -> bool:
    return False


def _queue_entries(orders: list[ProductionOrder]) -> dict[QueueScope, frozenset[_QueueEntry]]:
    entries: dict[QueueScope, set[_QueueEntry]] = {}
    for o in orders:
        entries.setdefault(queue_scope_key(o.machine_id, o.machine_pool_id), set()).add(
            (o.id, o.status, o.pinned, o.machine_id, o.machine_pool_id, o.queue_sequence)
        )
    return {scope: frozenset(queue) for scope, queue in entries.items()}


# Pre-run (machine_id, machine_pool_id, queue_sequence, planned_start, planned_end) per placed
# order id.
_BeforeSnapshot = dict[int, tuple[int | None, int | None, int, datetime | None, datetime | None]]


@dataclass
class _AutoPlanState:
    """Mutable state shared by execute()'s phases. `now` and `today` are
    set once by _seed_anchors and never re-sampled. `today` is the current
    day in the tenant's default timezone `zone`, the day every scheduling
    date is compared with: the exclude_todays_planned rule, which protects
    a worker's day, and the critical ratio ordering."""

    settings: AdminProductionSettings
    response_time_days: int
    all_machines: list[ProductionMachine]
    machines_by_id: dict[int, ProductionMachine]
    pools_by_id: dict[int, MachinePool]
    candidate_machine_ids: set[int]
    machine_fabrication_method_ids: dict[int, list[int]]
    qa_machine_ids: set[int]
    all_machine_fabrication_method_ids: dict[int, list[int]]
    pool_machine_ids: dict[int, list[int]]
    candidate_pool_ids: set[int]
    zone: tzinfo
    # Excluded only from eligibility, so a down machine's anchors and
    # bookkeeping remain for the MACHINE_DOWN skip-reason check.
    down_machine_ids: set[int] = field(default_factory=set)
    calendars: dict[int, MachineCalendar] = field(default_factory=dict)
    orders_by_id: dict[int, ProductionOrder] = field(default_factory=dict)
    contexts_by_order_id: dict[int, OrderSchedulingContext] = field(default_factory=dict)
    machine_anchors: dict[int, list[OrderSchedulingContext]] = field(default_factory=dict)
    now: datetime | None = None
    today: date | None = None
    candidate_orders: list[ProductionOrder] = field(default_factory=list)
    skipped: int = 0
    skipped_todays_planned: int = 0
    # Candidates the loop declined to place, unlike `skipped`, which counts
    # anchors.
    skipped_orders: list[AutoPlanSkippedOrder] = field(default_factory=list)
    pool_queue_lengths: dict[int, int] = field(default_factory=dict)
    machine_cursors: dict[int, datetime | None] = field(default_factory=dict)
    machine_queue_lengths: dict[int, int] = field(default_factory=dict)
    machine_booked_minutes: dict[int, int] = field(default_factory=dict)
    # Next free queue_sequence per scope. The queue lengths below are anchor
    # counts for tie-breaking and could collide with real values.
    machine_next_sequence: dict[int, int] = field(default_factory=dict)
    pool_next_sequence: dict[int, int] = field(default_factory=dict)
    # The queues as read, and the queue each candidate was read in.
    read_queues: dict[QueueScope, frozenset[_QueueEntry]] = field(default_factory=dict)
    candidate_origin: dict[int, QueueScope] = field(default_factory=dict)
    prefetch: SchedulingPrefetch | None = None
    lot_cache: dict[int, ProductionLot | None] = field(default_factory=dict)
    sibling_orders_by_position: dict[int, list[ProductionOrder]] = field(default_factory=dict)
    due_dates_by_lot: dict[int, dict[int, date | None]] = field(default_factory=dict)
    position_cache: dict[int, LotPosition | None] = field(default_factory=dict)
    selection_strategy: str = ""
    ordered_candidates: list[AutoPlanCandidate] = field(default_factory=list)
    # The queue place each candidate was read with, for the ones the run
    # does not place.
    candidate_original_sequence: dict[int, int] = field(default_factory=dict)
    before_snapshot: _BeforeSnapshot = field(default_factory=dict)
    touched_machine_ids: set[int | None] = field(default_factory=set)
    progress: AutoPlanProgressCallback | None = None


@dataclass(frozen=True)
class _Settlement:
    """What one attempt of the write phase writes: the orders with their new
    schedule fields, the placements it keeps, and the placements it drops
    because their queue changed while planning."""

    writes: list[ProductionOrder]
    kept: frozenset[int]
    changed: list[AutoPlanSkippedOrder]


def _emit(state: _AutoPlanState, event: AutoPlanProgress) -> None:
    """Reports progress if a callback is attached. A raising callback is
    logged and ignored, so a watching SSE consumer can never break the run."""
    if state.progress is None:
        return
    try:
        state.progress(event)
    except Exception as exc:  # a raising callback must never break the run
        log.warning("Auto-plan progress callback raised, ignoring: %r", exc)


def _snapshot_before(order: ProductionOrder, before_snapshot: _BeforeSnapshot) -> None:
    before_snapshot[order.id] = (
        order.machine_id,
        order.machine_pool_id,
        order.queue_sequence,
        order.planned_start,
        order.planned_end,
    )


def _progress_order(
    order: ProductionOrder,
    *,
    placed: bool,
    before_machine_id: int | None,
    before_machine_pool_id: int | None,
    reason: str | None = None,
) -> AutoPlanProgressOrder:
    return AutoPlanProgressOrder(
        order_id=order.id,
        production_order_number=order.production_order_number,
        lot_number=order.lot_number,
        made_item_part_number=order.made_item_part_number,
        made_item_revision=order.made_item_revision,
        placed=placed,
        before_machine_id=before_machine_id,
        after_machine_id=order.machine_id,
        before_machine_pool_id=before_machine_pool_id,
        after_machine_pool_id=order.machine_pool_id,
        reason=reason,
    )


def _placed_summary(
    order: ProductionOrder, before_snapshot: _BeforeSnapshot
) -> AutoPlanProgressOrder:
    before = before_snapshot[order.id]
    return _progress_order(
        order, placed=True, before_machine_id=before[0], before_machine_pool_id=before[1]
    )


def _record_unplaced(
    state: _AutoPlanState, order: ProductionOrder, skip_reason: str
) -> AutoPlanProgressOrder:
    """Files an unplaced candidate in the result with its skip reason and
    returns its progress event, which carries the same reason."""
    state.skipped_orders.append(
        AutoPlanSkippedOrder(
            order_id=order.id,
            production_order_number=order.production_order_number,
            reason=skip_reason,
        )
    )
    return _progress_order(
        order,
        placed=False,
        before_machine_id=order.machine_id,
        before_machine_pool_id=order.machine_pool_id,
        reason=skip_reason,
    )


def _report_dropped(state: _AutoPlanState, dropped: list[AutoPlanSkippedOrder]) -> None:
    """Streams a placing event for every placement the write dropped,
    reported as placed while placing, so the stream ends as the result does:
    the order unplaced with its skip reason, still in the queue it was read
    in. Called before the dropped placements leave `before_snapshot`."""
    total = len(state.ordered_candidates)
    for skipped in dropped:
        order = state.orders_by_id[skipped.order_id]
        machine_id, pool_id = state.before_snapshot[skipped.order_id][:2]
        _emit(
            state,
            AutoPlanProgress(
                stage="placing",
                current=total,
                total=total,
                order=AutoPlanProgressOrder(
                    order_id=order.id,
                    production_order_number=order.production_order_number,
                    lot_number=order.lot_number,
                    made_item_part_number=order.made_item_part_number,
                    made_item_revision=order.made_item_revision,
                    placed=False,
                    before_machine_id=machine_id,
                    after_machine_id=machine_id,
                    before_machine_pool_id=pool_id,
                    after_machine_pool_id=pool_id,
                    reason=skipped.reason,
                ),
            ),
        )


def _moved(diff: AutoPlanOrderDiff) -> bool:
    """Whether a placement changed where or when the order runs. A
    placement back into the same queue with the same window, a new queue
    place at most, is no move."""
    return (
        diff.before_machine_id != diff.after_machine_id
        or diff.before_machine_pool_id != diff.after_machine_pool_id
        or diff.before_planned_start != diff.after_planned_start
        or diff.before_planned_end != diff.after_planned_end
    )


def _resolve_pool(
    state: _AutoPlanState,
    ctx: OrderSchedulingContext,
    eligible_pool_ids: list[int],
    pool_machine_ids: dict[int, list[int]],
    now: datetime,
) -> tuple[int, int, datetime | None] | None:
    return resolve_pool_for_candidate(
        state.selection_strategy,
        ctx,
        eligible_pool_ids,
        pool_machine_ids,
        state.machine_cursors,
        state.machine_booked_minutes,
        state.calendars,
        now,
        state.pool_queue_lengths,
    )


def _pool_member_skip_reason(
    state: _AutoPlanState,
    ctx: OrderSchedulingContext,
    eligible_pool_ids: list[int],
    now: datetime,
) -> str:
    """Why no eligible pool had a member to trial: a scope gap, or, if the
    search succeeds with down members included, a down machine."""
    if state.down_machine_ids:
        pool_best_with_down = _resolve_pool(
            state, ctx, eligible_pool_ids, state.pool_machine_ids, now
        )
        if pool_best_with_down is not None:
            return AutoPlanSkipReason.MACHINE_DOWN.value
    return AutoPlanSkipReason.NO_ELIGIBLE_POOL_MEMBER.value


def _assign_pool(
    state: _AutoPlanState,
    order: ProductionOrder,
    pool_id: int,
    trial_member_id: int,
    trial_next_cursor: datetime | None,
) -> None:
    """Writes a pool placement. The winning member is never persisted; only
    its cursor and booked minutes advance."""
    new_sequence = state.pool_next_sequence.get(pool_id, 1)
    state.pool_next_sequence[pool_id] = new_sequence + 1
    state.pool_queue_lengths[pool_id] = state.pool_queue_lengths.get(pool_id, 0) + 1
    state.machine_cursors[trial_member_id] = trial_next_cursor
    state.machine_booked_minutes[trial_member_id] = (
        state.machine_booked_minutes.get(trial_member_id, 0) + order.estimated_duration_minutes
    )
    order.machine_pool_id = pool_id
    order.queue_sequence = new_sequence
    if order.pinned:
        order.pinned = False
    # The walk would keep a window inside the frozen window where it was.
    drop_planned_window(order)


def _eligible_machine_ids(
    cmd: AutoPlanCommand,
    state: _AutoPlanState,
    order: ProductionOrder,
    requires_qa_machine: bool,
    required_fabrication_method_ids: set[int],
) -> list[int]:
    pool = state.pools_by_id.get(order.machine_pool_id) if order.machine_pool_id else None
    return resolve_eligible_machine_ids(
        order_machine_pool_id=order.machine_pool_id,
        order_machine_id=order.machine_id,
        candidate_machine_ids=state.candidate_machine_ids,
        pool_machine_ids=set(pool.machine_ids) if pool else set(),
        machine_fabrication_method_ids=state.machine_fabrication_method_ids,
        required_fabrication_method_ids=required_fabrication_method_ids,
        assign_pool_machines=True,
        assign_machines=cmd.assign_machines,
        qa_machine_ids=state.qa_machine_ids,
        requires_qa_machine=requires_qa_machine,
    )


def _assign_machine(
    state: _AutoPlanState,
    order: ProductionOrder,
    machine_id: int,
    next_cursor: datetime | None,
) -> None:
    """Writes a machine placement. A pinned order only gets here with
    overwrite_pinned, so its pin is cleared."""
    new_sequence = state.machine_next_sequence[machine_id]
    state.machine_next_sequence[machine_id] = new_sequence + 1
    state.machine_queue_lengths[machine_id] += 1
    state.machine_cursors[machine_id] = next_cursor
    state.machine_booked_minutes[machine_id] = (
        state.machine_booked_minutes.get(machine_id, 0) + order.estimated_duration_minutes
    )
    order.machine_id = machine_id
    order.queue_sequence = new_sequence
    if order.pinned:
        order.pinned = False
    # The walk would keep a window inside the frozen window where it was.
    drop_planned_window(order)


def _settle(state: _AutoPlanState, current: dict[int, ProductionOrder]) -> _Settlement:
    """Matches the plan against the queues as read again under their locks.
    A placement whose queue of origin or destination changed is dropped. An
    order the run does not place, or whose placement was dropped, gets a
    queue place in the queue it was read in, unless that queue changed: a
    fresh one from the queue's counter when a kept placement went into the
    queue, since its old place may now belong to that placement, else the
    one it had. The orders written are copies of the rows read under the
    locks with only their schedule fields changed, so nothing the run did
    not decide is written back."""
    current_queues = _queue_entries(list(current.values()))
    changed_scopes = {
        scope
        for scope in state.read_queues.keys() | current_queues.keys()
        if state.read_queues.get(scope) != current_queues.get(scope)
    }

    writes: list[ProductionOrder] = []
    kept: set[int] = set()
    changed: list[AutoPlanSkippedOrder] = []
    written_scopes: set[QueueScope] = set()
    for order_id in state.before_snapshot:
        planned = state.orders_by_id[order_id]
        target = queue_scope_key(planned.machine_id, planned.machine_pool_id)
        if state.candidate_origin[order_id] in changed_scopes or target in changed_scopes:
            changed.append(
                AutoPlanSkippedOrder(
                    order_id=order_id,
                    production_order_number=planned.production_order_number,
                    reason=AutoPlanSkipReason.CHANGED_WHILE_PLANNING.value,
                )
            )
            continue
        row = copy(current[order_id])
        row.machine_id = planned.machine_id
        row.machine_pool_id = planned.machine_pool_id
        row.queue_sequence = planned.queue_sequence
        row.pinned = planned.pinned
        drop_planned_window(row)
        writes.append(row)
        kept.add(order_id)
        written_scopes.add(target)

    machine_next = dict(state.machine_next_sequence)
    pool_next = dict(state.pool_next_sequence)
    for order in state.candidate_orders:
        origin = state.candidate_origin[order.id]
        if order.id in kept or origin in changed_scopes:
            continue
        machine_id, pool_id = origin
        if origin in written_scopes and machine_id is not None:
            sequence = machine_next[machine_id]
            machine_next[machine_id] = sequence + 1
        elif origin in written_scopes and pool_id is not None:
            sequence = pool_next[pool_id]
            pool_next[pool_id] = sequence + 1
        else:
            sequence = state.candidate_original_sequence[order.id]
        row = copy(current[order.id])
        row.queue_sequence = sequence
        writes.append(row)
    return _Settlement(writes=writes, kept=frozenset(kept), changed=changed)


class AutoPlan:
    def __init__(
        self,
        repos: SchedulingRepos,
        machine_repo: IProductionMachineRepository,
        calendar_repo: IMachineCalendarRepository,
        settings_repo: IFulfillmentSettingsRepository,
        recompute_schedule: RecomputeMachineSchedule,
        pool_repo: IMachinePoolRepository | None = None,
        downtime_repo: IMachineDowntimeRepository | None = None,
        *,
        uow: IUnitOfWork,
        retryable: Callable[[BaseException], bool] = _never_retry,
    ) -> None:
        """`retryable` tells a database error that lost a race, after which
        the write phase runs once more."""
        self._repos = repos
        self._machines = machine_repo
        self._calendars = calendar_repo
        self._settings = settings_repo
        self._recompute = recompute_schedule
        self._pools = pool_repo
        self._downtimes = downtime_repo
        self._uow = uow
        self._retryable = retryable

    def _lot_position_due_dates(
        self,
        lot: ProductionLot,
        lot_target_date: date | None,
        default_external_lead_days: int,
        sibling_orders_by_position: dict[int, list[ProductionOrder]],
        order_items_by_position: dict[int, OrderItem],
    ) -> dict[int, date | None]:
        """Backward pass from prefetched data. The inputs are required so no
        caller can reintroduce per-lot queries."""
        sequences = [p.sequence for p in lot.positions]
        lead_days_by_sequence = {}
        for position in lot.positions:
            if position.kind == LotPositionKind.EXTERNAL:
                order_item = order_items_by_position.get(position.id)
                supplier_override = (
                    order_item.supplier_external_lead_time_days if order_item else None
                )
                lead_days_by_sequence[position.sequence] = resolve_position_lead_days(
                    position.steps, supplier_override, default_external_lead_days
                )
                continue
            sibling_orders = sibling_orders_by_position.get(position.id, [])
            total_minutes = sum(o.estimated_duration_minutes for o in sibling_orders)
            lead_days_by_sequence[position.sequence] = position_lead_days(
                position.kind, total_minutes, default_external_lead_days
            )
        return compute_position_due_dates(sequences, lead_days_by_sequence, lot_target_date)

    async def _load_machine_context(self, cmd: AutoPlanCommand) -> _AutoPlanState:
        settings = await self._settings.get_production()
        zone = await tenant_zone(self._settings)
        response_time_days = (
            cmd.response_time_days
            if cmd.response_time_days is not None
            else settings.response_time_days
        )
        # get_all(), because get_multi clamps to one page.
        all_machines = await self._machines.get_all()
        all_machines = [m for m in all_machines if not m.archived]
        machines_by_id = {m.id: m for m in all_machines}
        pools_by_id = {}
        if self._pools is not None:
            all_pools = await self._pools.get_all()
            pools_by_id = {p.id: p for p in all_pools if not p.archived}
        candidate_machine_ids = (
            set(cmd.machine_ids) if cmd.machine_ids else {m.id for m in all_machines}
        )
        candidate_machine_ids &= set(machines_by_id.keys())
        machine_fabrication_method_ids = {
            mid: machines_by_id[mid].fabrication_method_ids for mid in candidate_machine_ids
        }
        qa_machine_ids = {mid for mid in candidate_machine_ids if machines_by_id[mid].is_qa_machine}
        # A pool's capability does not depend on this run's machine scope.
        all_machine_fabrication_method_ids = {m.id: m.fabrication_method_ids for m in all_machines}
        pool_machine_ids = {pid: pool.machine_ids for pid, pool in pools_by_id.items()}
        candidate_pool_ids = set(pools_by_id.keys())

        down_machine_ids: set[int] = set()
        if self._downtimes is not None:
            all_relevant_machine_ids = candidate_machine_ids | {
                mid for ids in pool_machine_ids.values() for mid in ids
            }
            if all_relevant_machine_ids:
                down_machine_ids = set(
                    (
                        await self._downtimes.get_open_by_machine_ids(
                            list(all_relevant_machine_ids), started_by=now_utc()
                        )
                    ).keys()
                )

        return _AutoPlanState(
            settings=settings,
            response_time_days=response_time_days,
            all_machines=all_machines,
            machines_by_id=machines_by_id,
            pools_by_id=pools_by_id,
            candidate_machine_ids=candidate_machine_ids,
            machine_fabrication_method_ids=machine_fabrication_method_ids,
            qa_machine_ids=qa_machine_ids,
            all_machine_fabrication_method_ids=all_machine_fabrication_method_ids,
            pool_machine_ids=pool_machine_ids,
            candidate_pool_ids=candidate_pool_ids,
            down_machine_ids=down_machine_ids,
            zone=zone,
        )

    async def _lock_queue_scopes(self, state: _AutoPlanState) -> None:
        """Locks every scope a candidate might land in before the write reads
        its queues again, since queue_sequence uniqueness across transactions
        depends on it. Sorted order prevents deadlocks; every candidate scope
        is locked, the ones the plan leaves alone included, because a changed
        queue is only known after the locked read."""
        # The unassigned queue too, whose orders the run loads and may assign.
        scopes = sorted(
            {(mid, None) for mid in state.candidate_machine_ids}
            | {(None, pid) for pid in state.candidate_pool_ids}
            | {(None, None)},
            key=lambda s: (s[0] is None, s[0] or 0, s[1] is None, s[1] or 0),
        )
        for machine_id, pool_id in scopes:
            await self._repos.orders.lock_queue_scope(machine_id, pool_id)
        # The machines were read before their queue locks, and an archive
        # takes the same lock before it counts a machine's orders, so a
        # machine archived in between is only seen now.
        current = await self._machines.get_by_ids(sorted(state.candidate_machine_ids))
        archived = sorted(m.internal_name for m in current if m.archived)
        if archived:
            raise ConcurrentModificationError(
                f"Machine {', '.join(archived)} was archived while Auto-Plan was preparing. "
                "Run Auto-Plan again."
            )

    async def _build_calendars(self, state: _AutoPlanState) -> None:
        """The candidate machines' calendars with their downtimes cut out, so
        a placement never lands in a maintenance window that starts later; a
        machine down right now is excluded from the run besides."""
        state.calendars = await build_machine_calendars(
            list(state.candidate_machine_ids),
            self._calendars,
            state.settings.default_weekly_hours,
            downtime_repo=self._downtimes,
            now=state.now,
            zone=state.zone,
        )

    async def _build_contexts(self, state: _AutoPlanState) -> None:
        """Loads the orders of every candidate machine plus machine-less ones
        in one query, without a lock, and builds their contexts per machine
        group. The placement works on copies, so the queues as read stay
        what the write compares against."""
        orders_by_id: dict[int, ProductionOrder] = {}
        contexts_by_order_id: dict[int, OrderSchedulingContext] = {}
        machine_anchors: dict[int, list[OrderSchedulingContext]] = {
            mid: [] for mid in state.candidate_machine_ids
        }
        machine_scopes: list[int | None] = [*state.candidate_machine_ids, None]
        orders_by_machine: dict[int | None, list[ProductionOrder]] = {
            scope: [] for scope in machine_scopes
        }
        loaded = [copy(o) for o in await self._repos.orders.get_live_by_machine_ids(machine_scopes)]
        state.read_queues = _queue_entries(loaded)
        for order in loaded:
            if order.machine_id in orders_by_machine:
                orders_by_machine[order.machine_id].append(order)
        prefetch = await prefetch_scheduling_data(
            [o for group in orders_by_machine.values() for o in group],
            self._repos,
            self._pools,
            zone=state.zone,
            today=state.today,
        )
        for machine_id in machine_scopes:
            group = orders_by_machine[machine_id]
            for order in group:
                orders_by_id[order.id] = order
            for ctx in await build_contexts(
                group,
                self._repos,
                machine=state.machines_by_id[machine_id] if machine_id is not None else None,
                response_time_days=state.response_time_days,
                pool_repo=self._pools,
                down_machine_ids=state.down_machine_ids,
                prefetch=prefetch,
                internal_handoff_minutes=state.settings.internal_handoff_minutes,
                zone=state.zone,
            ):
                contexts_by_order_id[ctx.order_id] = ctx

        state.orders_by_id = orders_by_id
        state.contexts_by_order_id = contexts_by_order_id
        state.machine_anchors = machine_anchors
        state.prefetch = prefetch

    async def _seed_anchors(self, cmd: AutoPlanCommand, state: _AutoPlanState) -> None:
        """Classifies orders into candidates and anchors and seeds each
        machine's cursor from its anchors."""
        assert state.now is not None and state.today is not None  # set by execute
        now = state.now
        self._classify_orders(cmd, state, state.today)
        self._seed_machine_cursors(state, now)

    def _classify_orders(self, cmd: AutoPlanCommand, state: _AutoPlanState, today: date) -> None:
        """Splits loaded orders into movable candidates and fixed anchors.
        An order counts as today's planned when its window touches `today`,
        a day of the tenant's timezone."""
        candidate_orders: list[ProductionOrder] = []
        skipped = 0
        skipped_todays_planned = 0
        # Anchor counts and highest anchor sequence per pool; candidates are
        # excluded because they are re-placed.
        pool_queue_lengths: dict[int, int] = {}
        pool_anchor_max_sequence: dict[int, int] = {}
        for order in state.orders_by_id.values():
            in_scope = cmd.lot_id is None or order.lot_id == cmd.lot_id
            todays_planned = cmd.exclude_todays_planned and production_order_touches_date(
                order.planned_start, order.planned_end, today, zone=state.zone
            )
            if self._is_movable_candidate(
                cmd, order, in_scope, todays_planned
            ) and self._takes_part(cmd, state, order):
                candidate_orders.append(order)
                state.candidate_origin[order.id] = queue_scope_key(
                    order.machine_id, order.machine_pool_id
                )
                state.candidate_original_sequence[order.id] = order.queue_sequence
                continue
            if order.pinned or order.status == ProductionOrderStatus.IN_PROGRESS:
                skipped += 1
            elif in_scope and order.status == ProductionOrderStatus.QUEUED and todays_planned:
                skipped_todays_planned += 1
            self._record_anchor(state, order, pool_queue_lengths, pool_anchor_max_sequence)
        state.candidate_orders = candidate_orders
        state.skipped = skipped
        state.skipped_todays_planned = skipped_todays_planned
        state.pool_queue_lengths = pool_queue_lengths
        state.pool_next_sequence = {
            pid: pool_anchor_max_sequence.get(pid, 0) + 1 for pid in state.candidate_pool_ids
        }

    def _is_movable_candidate(
        self, cmd: AutoPlanCommand, order: ProductionOrder, in_scope: bool, todays_planned: bool
    ) -> bool:
        """True for a QUEUED in-scope order that is not pinned (unless
        overwrite_pinned), not excluded as today's, and at the pools level
        not machine-resolved."""
        return (
            in_scope
            and order.status == ProductionOrderStatus.QUEUED
            and (not order.pinned or cmd.overwrite_pinned)
            and not todays_planned
            and not (cmd.planning_level == "pools" and order.machine_id is not None)
        )

    def _takes_part(
        self, cmd: AutoPlanCommand, state: _AutoPlanState, order: ProductionOrder
    ) -> bool:
        """Whether a movable order without a machine is one the run plans
        and reports. A manual or unassigned inspection step has no machine
        decision, since the walk dates it, so it is left alone unless it
        waits on material, which is reported. A run limited to some
        machines leaves an order alone that only machines outside the run
        could take, such as another team's work: at the pools level an
        order whose eligible pools have no member in the run, at the
        machines level an order no machine in the run could take. An order
        nothing at all could take stays in, so its skip is reported."""
        if order.machine_id is not None:
            return True
        ctx = state.contexts_by_order_id.get(order.id)
        if ctx is None:
            return True
        if ctx.is_manual_step and not is_unplannable_for_missing_material(ctx):
            return False
        if state.candidate_machine_ids >= set(state.machines_by_id):
            return True
        assert state.prefetch is not None  # set by _build_contexts, which always runs first
        lot = state.prefetch.lots_by_id.get(order.lot_id)
        position = (
            next((p for p in lot.positions if p.id == order.lot_position_id), None)
            if lot is not None
            else None
        )
        steps = position.steps if position else []
        requires_qa_machine = position_requires_qa_machine(steps)
        required = {s.fabrication_method_id for s in steps if s.fabrication_method_id is not None}
        # QA work takes the machine path at the pools level too.
        if cmd.planning_level == "pools" and not requires_qa_machine:
            eligible_pool_ids = resolve_eligible_pool_ids(
                candidate_pool_ids=state.candidate_pool_ids,
                pool_machine_ids=state.pool_machine_ids,
                machine_fabrication_method_ids=state.all_machine_fabrication_method_ids,
                required_fabrication_method_ids=required,
            )
            return not eligible_pool_ids or any(
                state.candidate_machine_ids.intersection(state.pool_machine_ids[pid])
                for pid in eligible_pool_ids
            )
        pool = state.pools_by_id.get(order.machine_pool_id) if order.machine_pool_id else None
        all_qa_ids = {m.id for m in state.all_machines if m.is_qa_machine}

        def eligible(machine_ids: set[int]) -> list[int]:
            return resolve_eligible_machine_ids(
                order_machine_pool_id=order.machine_pool_id,
                order_machine_id=None,
                candidate_machine_ids=machine_ids,
                pool_machine_ids=set(pool.machine_ids) if pool else set(),
                machine_fabrication_method_ids=state.all_machine_fabrication_method_ids,
                required_fabrication_method_ids=required,
                assign_pool_machines=True,
                assign_machines=True,
                qa_machine_ids=all_qa_ids,
                requires_qa_machine=requires_qa_machine,
            )

        return bool(eligible(state.candidate_machine_ids)) or not eligible(
            set(state.machines_by_id)
        )

    def _record_anchor(
        self,
        state: _AutoPlanState,
        order: ProductionOrder,
        pool_queue_lengths: dict[int, int],
        pool_anchor_max_sequence: dict[int, int],
    ) -> None:
        """Files an anchor under its machine, or only counts it for its pool."""
        if order.machine_id in state.machine_anchors and order.id in state.contexts_by_order_id:
            state.machine_anchors[order.machine_id].append(state.contexts_by_order_id[order.id])
        elif order.machine_id is None and order.machine_pool_id is not None:
            pool_queue_lengths[order.machine_pool_id] = (
                pool_queue_lengths.get(order.machine_pool_id, 0) + 1
            )
            pool_anchor_max_sequence[order.machine_pool_id] = max(
                pool_anchor_max_sequence.get(order.machine_pool_id, 0), order.queue_sequence
            )

    def _seed_machine_cursors(self, state: _AutoPlanState, now: datetime) -> None:
        """Seeds each machine's cursor, queue length and booked minutes from
        its anchors once. Candidates are only appended, so trials never
        re-walk a queue."""
        machine_cursors: dict[int, datetime | None] = {}
        machine_queue_lengths: dict[int, int] = {}
        machine_booked_minutes: dict[int, int] = {}
        machine_next_sequence: dict[int, int] = {}
        for machine_id, anchors in state.machine_anchors.items():
            cursor: datetime | None = None
            for anchor_ctx in sorted(anchors, key=lambda c: c.queue_sequence):
                _, _, cursor = advance_machine_queue(
                    anchor_ctx, cursor, state.calendars[machine_id], now
                )
            machine_cursors[machine_id] = cursor
            machine_queue_lengths[machine_id] = len(anchors)
            machine_booked_minutes[machine_id] = sum(a.estimated_duration_minutes for a in anchors)
            # Seeded from the highest anchor sequence, not the anchor count,
            # because an anchor can sit above candidates in the sequence.
            machine_next_sequence[machine_id] = (
                max((a.queue_sequence for a in anchors), default=0) + 1
            )
        state.machine_cursors = machine_cursors
        state.machine_queue_lengths = machine_queue_lengths
        state.machine_booked_minutes = machine_booked_minutes
        state.machine_next_sequence = machine_next_sequence

    async def _score_candidates(self, cmd: AutoPlanCommand, state: _AutoPlanState) -> None:
        # Due dates per candidate from the backward pass, cached per lot.
        prefetch = state.prefetch
        assert prefetch is not None  # set by _build_contexts, which always runs first
        lot_cache: dict[int, ProductionLot | None] = {
            order.lot_id: prefetch.lots_by_id.get(order.lot_id) for order in state.candidate_orders
        }
        sibling_orders_by_position = prefetch.sibling_orders_by_position
        order_items_by_position = prefetch.order_items_by_position
        target_date_by_lot = dict(prefetch.target_date_by_lot)

        due_dates_by_lot: dict[int, dict[int, date | None]] = {}
        position_cache: dict[int, LotPosition | None] = {}
        auto_plan_candidates = []
        for order in state.candidate_orders:
            lot = lot_cache[order.lot_id]
            if lot is None:
                continue
            if order.lot_id not in due_dates_by_lot:
                if order.lot_id not in target_date_by_lot:
                    target_date_by_lot[order.lot_id] = await resolve_lot_target_date(
                        lot, self._repos
                    )
                due_dates_by_lot[order.lot_id] = self._lot_position_due_dates(
                    lot,
                    target_date_by_lot[order.lot_id],
                    state.settings.default_external_lead_days,
                    sibling_orders_by_position,
                    order_items_by_position,
                )
            position = next((p for p in lot.positions if p.id == order.lot_position_id), None)
            position_cache[order.id] = position
            due_date = due_dates_by_lot[order.lot_id].get(position.sequence) if position else None
            auto_plan_candidates.append(
                AutoPlanCandidate(
                    order_id=order.id,
                    urgency_rank=_URGENCY_RANK.get(order.priority, 0),
                    position_due_date=due_date,
                    created_order=order.id,
                    estimated_duration_minutes=order.estimated_duration_minutes,
                    lot_id=order.lot_id,
                    position_sequence=position.sequence if position else 0,
                )
            )

        ordering_strategy, selection_strategy = resolve_algorithm_strategies(cmd.algorithm)
        assert state.today is not None  # set by execute before any read
        ordered_candidates = sort_candidates(auto_plan_candidates, ordering_strategy, state.today)

        state.lot_cache = lot_cache
        state.sibling_orders_by_position = sibling_orders_by_position
        state.due_dates_by_lot = due_dates_by_lot
        state.position_cache = position_cache
        state.selection_strategy = selection_strategy
        state.ordered_candidates = ordered_candidates

    async def _place_candidates(self, cmd: AutoPlanCommand, state: _AutoPlanState) -> None:
        """Greedy trial loop shell: progress events and skipped-order
        bookkeeping, with no transaction open. Each candidate's trial lives in
        _attempt_placement."""
        assert state.now is not None  # set by execute before any read

        before_snapshot: _BeforeSnapshot = {}
        touched_machine_ids: set[int | None] = set()

        total_candidates = len(state.ordered_candidates)
        _emit(state, AutoPlanProgress(stage="placing", current=0, total=total_candidates))

        # The trials are pure computation over loaded entities, so they run in
        # a worker thread and keep the event loop free; progress goes back
        # through the loop, whose stream queue is not thread-safe.
        reporter = state.progress
        if reporter is not None:
            state.progress = lambda event: from_thread.run_sync(reporter, event)
        try:
            await to_thread.run_sync(
                self._place_all, cmd, state, before_snapshot, touched_machine_ids
            )
        finally:
            state.progress = reporter

        state.before_snapshot = before_snapshot
        state.touched_machine_ids = touched_machine_ids

    def _place_all(
        self,
        cmd: AutoPlanCommand,
        state: _AutoPlanState,
        before_snapshot: _BeforeSnapshot,
        touched_machine_ids: set[int | None],
    ) -> None:
        """The greedy trial of every candidate, in order."""
        total_candidates = len(state.ordered_candidates)
        for index, candidate in enumerate(state.ordered_candidates):
            order = state.orders_by_id[candidate.order_id]
            outcome = self._attempt_placement(
                cmd, state, order, before_snapshot, touched_machine_ids
            )
            summary = (
                _record_unplaced(state, order, outcome) if isinstance(outcome, str) else outcome
            )
            _emit(
                state,
                AutoPlanProgress(
                    stage="placing",
                    current=index + 1,
                    total=total_candidates,
                    order=summary,
                ),
            )

    def _attempt_placement(
        self,
        cmd: AutoPlanCommand,
        state: _AutoPlanState,
        order: ProductionOrder,
        before_snapshot: _BeforeSnapshot,
        touched_machine_ids: set[int | None],
    ) -> AutoPlanProgressOrder | str:
        """One candidate's placement trial: guard clauses first, then a
        pool or machine placement branch. Returns the placed summary, or
        the skip reason of a candidate it cannot place."""
        assert state.now is not None  # set by execute before any read
        now = state.now
        ctx = state.contexts_by_order_id[order.id]

        # It would get no dates on any trial, so it is reported instead.
        if is_unplannable_for_missing_material(ctx):
            return AutoPlanSkipReason.WAITING_ON_MATERIAL.value

        # Manual and unassigned inspection steps have no machine decision,
        # so _takes_part keeps them out of the candidates.
        assert not (ctx.is_manual_step and order.machine_id is None)

        position = state.position_cache.get(order.id)
        steps = position.steps if position else []
        requires_qa_machine = position_requires_qa_machine(steps)
        required_fabrication_method_ids = {
            s.fabrication_method_id for s in steps if s.fabrication_method_id is not None
        }

        # QA work is never pool-eligible and always takes the machine path.
        if cmd.planning_level == "pools" and not requires_qa_machine:
            return self._place_in_pool(
                state,
                order,
                ctx,
                required_fabrication_method_ids,
                before_snapshot,
                touched_machine_ids,
                now,
            )

        return self._place_on_machine(
            cmd,
            state,
            order,
            ctx,
            requires_qa_machine,
            required_fabrication_method_ids,
            before_snapshot,
            touched_machine_ids,
            now,
        )

    def _place_in_pool(
        self,
        state: _AutoPlanState,
        order: ProductionOrder,
        ctx: OrderSchedulingContext,
        required_fabrication_method_ids: set[int],
        before_snapshot: _BeforeSnapshot,
        touched_machine_ids: set[int | None],
        now: datetime,
    ) -> AutoPlanProgressOrder | str:
        """Assigns a fabrication candidate to a pool without a machine."""
        eligible_pool_ids = resolve_eligible_pool_ids(
            candidate_pool_ids=state.candidate_pool_ids,
            pool_machine_ids=state.pool_machine_ids,
            machine_fabrication_method_ids=state.all_machine_fabrication_method_ids,
            required_fabrication_method_ids=required_fabrication_method_ids,
        )
        if not eligible_pool_ids:
            return AutoPlanSkipReason.NO_ELIGIBLE_POOL.value

        # Down members are filtered here only; the skip reason needs them.
        available_pool_machine_ids = {
            pid: [mid for mid in members if mid not in state.down_machine_ids]
            for pid, members in state.pool_machine_ids.items()
        }
        pool_best = _resolve_pool(state, ctx, eligible_pool_ids, available_pool_machine_ids, now)
        if pool_best is None:
            return _pool_member_skip_reason(state, ctx, eligible_pool_ids, now)
        best_pool_id, trial_member_id, trial_next_cursor = pool_best

        _snapshot_before(order, before_snapshot)
        # Adds the None bucket; the set only feeds the progress count.
        touched_machine_ids.add(order.machine_id)
        _assign_pool(state, order, best_pool_id, trial_member_id, trial_next_cursor)
        return _placed_summary(order, before_snapshot)

    def _place_on_machine(
        self,
        cmd: AutoPlanCommand,
        state: _AutoPlanState,
        order: ProductionOrder,
        ctx: OrderSchedulingContext,
        requires_qa_machine: bool,
        required_fabrication_method_ids: set[int],
        before_snapshot: _BeforeSnapshot,
        touched_machine_ids: set[int | None],
        now: datetime,
    ) -> AutoPlanProgressOrder | str:
        """Places a candidate on a concrete machine (also QA in pools mode)."""
        eligible_machine_ids = _eligible_machine_ids(
            cmd, state, order, requires_qa_machine, required_fabrication_method_ids
        )
        # Comparing before and after removing down machines tells
        # NO_ELIGIBLE_MACHINE apart from MACHINE_DOWN.
        available_machine_ids = [
            mid for mid in eligible_machine_ids if mid not in state.down_machine_ids
        ]

        best = resolve_machine_for_candidate(
            state.selection_strategy,
            ctx,
            available_machine_ids,
            state.machine_cursors,
            state.machine_booked_minutes,
            state.calendars,
            now,
            state.machine_queue_lengths,
        )
        if best is None:
            return (
                AutoPlanSkipReason.MACHINE_DOWN.value
                if eligible_machine_ids and not available_machine_ids
                else AutoPlanSkipReason.NO_ELIGIBLE_MACHINE.value
            )
        best_machine_id, best_next_cursor = best

        _snapshot_before(order, before_snapshot)
        touched_machine_ids.add(order.machine_id)
        touched_machine_ids.add(best_machine_id)
        _assign_machine(state, order, best_machine_id, best_next_cursor)
        return _placed_summary(order, before_snapshot)

    async def _lock_queue_orders(self, state: _AutoPlanState) -> dict[int, ProductionOrder]:
        """The live orders of every queue the run may write, read again under
        the queue locks, which keep orders from entering these queues. The
        queued ones are locked and read once more, so a start, a cancel or a
        pin that committed before their lock is seen."""
        machine_scopes: list[int | None] = [*state.candidate_machine_ids, None]
        loaded = await self._repos.orders.get_live_by_machine_ids(machine_scopes)
        queued_ids = sorted(o.id for o in loaded if o.status == ProductionOrderStatus.QUEUED)
        if queued_ids:
            await self._repos.orders.lock_for_update(queued_ids)
            loaded = await self._repos.orders.get_live_by_machine_ids(machine_scopes)
        return {o.id: o for o in loaded}

    async def _write_once(self, state: _AutoPlanState) -> _Settlement:
        await self._lock_queue_scopes(state)
        settlement = _settle(state, await self._lock_queue_orders(state))
        # Every order written is shifted to a disjoint negative queue_sequence
        # first, and every value written is unique within its scope, so the
        # rows can be written together in any order.
        await self._repos.orders.shift_queue_sequence([o.id for o in settlement.writes])
        await self._repos.orders.save_schedule(settlement.writes)
        await self._uow.commit()
        return settlement

    async def _write_plan(self, state: _AutoPlanState) -> None:
        """The write phase. A lost race rolls the attempt back and runs it
        once more after a short pause, matching the plan against the queues
        as they are then; a second lost race is raised."""
        for attempt in range(2):
            try:
                settlement = await self._write_once(state)
            except Exception as exc:
                if attempt or not self._retryable(exc):
                    raise
                await self._uow.rollback()
                log.warning("Auto-Plan lost a race while writing its plan and writes it once more.")
                await asyncio.sleep(random.uniform(*_RETRY_DELAY_SECONDS))
                continue
            _report_dropped(state, settlement.changed)
            state.before_snapshot = {
                order_id: before
                for order_id, before in state.before_snapshot.items()
                if order_id in settlement.kept
            }
            state.touched_machine_ids = {
                machine_id
                for order_id, before in state.before_snapshot.items()
                for machine_id in (before[0], state.orders_by_id[order_id].machine_id)
            }
            state.skipped_orders.extend(settlement.changed)
            return

    async def _build_result(self, actor: User, state: _AutoPlanState) -> AutoPlanResult:
        await self._recompute_touched(state)
        _emit(state, AutoPlanProgress(stage="finalizing"))
        proposals = await self._build_proposals(state)
        moved = sum(1 for p in proposals if _moved(p))

        log.info(
            f"Ran the auto-planner: {moved} order(s) moved, "
            f"{state.skipped} pinned/in-progress/out-of-scope order(s) left untouched, "
            f"{state.skipped_todays_planned} today's-planned order(s) excluded, "
            f"{len(state.skipped_orders)} candidate(s) left unplaced."
        )

        return AutoPlanResult(
            proposals=proposals,
            skipped_pinned_or_in_progress=state.skipped,
            skipped_todays_planned=state.skipped_todays_planned,
            skipped=state.skipped_orders,
        )

    async def _recompute_touched(self, state: _AutoPlanState) -> None:
        """Runs one global recompute if the run touched anything. The plan
        is committed by then, so a failed walk is logged and rolled back
        rather than answered as an error; the proposals read the committed
        rows, and the next walk dates them."""
        total_touched = len(state.touched_machine_ids)
        _emit(state, AutoPlanProgress(stage="recomputing", current=0, total=total_touched))
        if not total_touched:
            return
        try:
            await self._recompute.execute_all(
                response_time_days=state.response_time_days,
                settings=state.settings,
            )
        except Exception:
            log.exception(
                "Schedule recompute failed after Auto-Plan; the plan itself is committed."
            )
            await self._uow.rollback()
        _emit(
            state,
            AutoPlanProgress(stage="recomputing", current=total_touched, total=total_touched),
        )

    async def _build_proposals(self, state: _AutoPlanState) -> list[AutoPlanOrderDiff]:
        """Diffs every placed order's pre-run snapshot against its freshly reloaded row."""
        proposals = []
        refreshed_by_id = (
            {o.id: o for o in await self._repos.orders.get_by_ids(list(state.before_snapshot))}
            if state.before_snapshot
            else {}
        )
        for order_id, (
            before_mid,
            before_pool_id,
            before_seq,
            before_start,
            before_end,
        ) in state.before_snapshot.items():
            refreshed = refreshed_by_id.get(order_id)
            if refreshed is None:
                continue
            proposals.append(
                AutoPlanOrderDiff(
                    order_id=refreshed.id,
                    production_order_number=refreshed.production_order_number,
                    lot_number=refreshed.lot_number,
                    made_item_part_number=refreshed.made_item_part_number,
                    made_item_revision=refreshed.made_item_revision,
                    before_machine_id=before_mid,
                    after_machine_id=refreshed.machine_id,
                    before_machine_pool_id=before_pool_id,
                    after_machine_pool_id=refreshed.machine_pool_id,
                    before_queue_sequence=before_seq,
                    after_queue_sequence=refreshed.queue_sequence,
                    before_planned_start=before_start,
                    before_planned_end=before_end,
                    after_planned_start=refreshed.planned_start,
                    after_planned_end=refreshed.planned_end,
                    conflicts=[],
                )
            )
        return proposals

    async def execute(
        self,
        actor: User,
        cmd: AutoPlanCommand,
        progress: AutoPlanProgressCallback | None = None,
    ) -> AutoPlanResult:
        """`progress` is an optional live-progress callback (see _emit)."""
        ProductionOrderRules.assert_can_assign(actor)
        state = await self._load_machine_context(cmd)
        state.progress = progress
        # One clock read for the run, so the calendars, the contexts and the
        # anchors agree on now and on today.
        state.now = now_utc()
        state.today = state.now.astimezone(state.zone).date()
        _emit(state, AutoPlanProgress(stage="preparing"))
        await self._build_calendars(state)
        _emit(state, AutoPlanProgress(stage="loading_orders"))
        await self._build_contexts(state)
        await self._seed_anchors(cmd, state)
        _emit(state, AutoPlanProgress(stage="scoring"))
        await self._score_candidates(cmd, state)
        # The reads are done; ending their transaction keeps the placement
        # from sitting idle in one, and no lock is held while it runs.
        await self._uow.commit()
        await self._place_candidates(cmd, state)
        await self._write_plan(state)
        return await self._build_result(actor, state)
