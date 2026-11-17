"""
RecomputeMachineSchedule.execute_all() re-walks the entire schedule in one pass via
scheduling.schedule_all, rather than one walk per machine. This
suite covers the behaviors of that unified walk:

  - a pool order floating onto a member machine is placed strictly after
    that machine's own machine-assigned commitments (the shared
    machine_cursors), and the winning member is never written onto the
    order itself;
  - every walked order's dates are persisted, and the pinned/non-pinned
    planned_by_id attribution rule holds;
  - an order left on a since-deleted machine (delete_machine.py does not
    reassign its orders) is still walked and dated, even though
    IProductionMachineRepository no longer resolves that id at all;
  - a pool id that can't be resolved degrades to the same
    schedule_unassigned_orders treatment schedule_all's own docstring
    describes (dateless, no NO_MACHINE_ASSIGNED flag);
  - execute_all() commits exactly once regardless of how many
    machines/pools/buckets were touched.

Fakes are imported from tests/unit/auto_plan/ (tests/unit/__init__.py makes
tests.unit a proper package) rather than duplicated; FakeOrderRepo there
already grew get_all_non_terminal() for this same reason, so the two
files can't quietly drift on what the port surface looks like.

Coalescing (generation_counter/recompute_lock, both optional constructor
args; see recompute_machine_schedule.py's module docstring): every test
above this point constructs RecomputeMachineSchedule via build_recompute()
without either, which is exactly "no coordinator wired" and reduces
execute_all() to the plain, always-walk behavior those tests assert. The
tests below this point cover
the coalescing behavior itself, with FakeGenerationCounter/FakeRecomputeLock
fakes: (a) skip when a concurrent walk already covers this call's own
generation, (b) walk-and-record-processed when it doesn't, (c) fail-open
when the counter raises, (d) the exact call/sampling order the module
docstring's correctness argument depends on.
"""

from contextlib import asynccontextmanager
from datetime import UTC
from datetime import datetime

from src.modules.fulfillment.application.services.scheduling_context import SchedulingRepos
from src.modules.fulfillment.application.use_cases.production_schedule.recompute_machine_schedule import (
    RecomputeMachineSchedule,
)
from src.modules.fulfillment.domain.entities.admin_settings.production import (
    AdminProductionSettings,
)
from src.modules.fulfillment.domain.entities.machine_pool import MachinePool
from src.modules.fulfillment.domain.entities.production_lot import ProductionLot
from src.modules.fulfillment.domain.entities.production_machine import ProductionMachine
from src.modules.fulfillment.domain.entities.production_order import ProductionOrder
from src.modules.fulfillment.domain.value_objects.schedule_conflict import ScheduleConflictReason
from tests.unit._tenant_settings import TenantSettings
from tests.unit.auto_plan._helpers import DEFAULT_WEEKLY_HOURS
from tests.unit.auto_plan._helpers import make_lot
from tests.unit.auto_plan._helpers import make_machine
from tests.unit.auto_plan._helpers import make_order
from tests.unit.auto_plan._helpers import make_pool
from tests.unit.auto_plan.fakes import FakeCalendarRepo
from tests.unit.auto_plan.fakes import FakeEmptyRepo
from tests.unit.auto_plan.fakes import FakeLotRepo
from tests.unit.auto_plan.fakes import FakeMachineRepo
from tests.unit.auto_plan.fakes import FakeOrderRepo
from tests.unit.auto_plan.fakes import FakePoolRepo
from tests.unit.auto_plan.fakes import FakeSettingsRepo
from tests.unit.fakes import FakeUnitOfWork


class CountingUnitOfWork(FakeUnitOfWork):
    """Same no-op semantics as FakeUnitOfWork, plus a call counter that
    proves execute_all() commits twice per call regardless of how many
    machines/pools/buckets it touched: once to end the reads before the
    CPU phase and once for the whole write."""

    def __init__(self) -> None:
        super().__init__()
        self.commit_calls = 0

    async def commit(self) -> None:
        self.commit_calls += 1


class FakeGenerationCounter:
    """Fake IScheduleRecomputeGenerationCounter: a plain in-memory counter
    plus a call log (`calls`), so tests can assert both the coalescing
    outcome and the exact call order the module docstring's correctness
    argument depends on (test (d) below).

    `raise_on` names methods that should raise instead of running, standing
    in for a Redis error at a specific point in the sequence; used by the
    fail-open tests (c)."""

    def __init__(
        self,
        *,
        initial_generation: int = 0,
        initial_processed: int = 0,
        raise_on: frozenset[str] = frozenset(),
    ) -> None:
        self._generation = initial_generation
        self._processed = initial_processed
        self._raise_on = raise_on
        self.calls: list[str] = []

    @property
    def processed(self) -> int:
        """The generation last marked processed, read without recording a call, for assertions."""
        return self._processed

    def _maybe_raise(self, name: str) -> None:
        self.calls.append(name)
        if name in self._raise_on:
            raise RuntimeError(f"Redis unavailable ({name})")

    async def increment_generation(self) -> int:
        self._maybe_raise("increment_generation")
        self._generation += 1
        return self._generation

    async def current_generation(self) -> int:
        self._maybe_raise("current_generation")
        return self._generation

    async def processed_generation(self) -> int:
        self._maybe_raise("processed_generation")
        return self._processed

    async def mark_processed(self, generation: int) -> None:
        self._maybe_raise("mark_processed")
        self._processed = generation


class FakeRecomputeLock:
    """Fake IScheduleRecomputeLock: never actually blocks (no real
    concurrency in a unit test), just counts how many times it was
    entered/exited so a test can confirm the lock really was (or wasn't)
    taken."""

    def __init__(self) -> None:
        self.enter_count = 0
        self.exit_count = 0

    @asynccontextmanager
    async def lock(self):  # type: ignore[no-untyped-def]
        self.enter_count += 1
        try:
            yield
        finally:
            self.exit_count += 1


def build_recompute(
    lots: list[ProductionLot],
    orders: list[ProductionOrder],
    machines: list[ProductionMachine],
    pools: list[MachinePool] | None = None,
    response_time_days: int = 0,
    uow: FakeUnitOfWork | None = None,
    generation_counter: FakeGenerationCounter | None = None,
    recompute_lock: FakeRecomputeLock | None = None,
) -> tuple[RecomputeMachineSchedule, FakeOrderRepo, FakeUnitOfWork]:
    order_repo = FakeOrderRepo(orders)
    repos = SchedulingRepos(
        orders=order_repo,  # type: ignore[arg-type]
        lots=FakeLotRepo(lots),  # type: ignore[arg-type]
        order_items=FakeEmptyRepo(),  # type: ignore[arg-type]
        source_item_demands=FakeEmptyRepo(),  # type: ignore[arg-type]
        source_item_allocations=FakeEmptyRepo(),  # type: ignore[arg-type]
        made_item_allocations=FakeEmptyRepo(),  # type: ignore[arg-type]
        made_item_demands=FakeEmptyRepo(),  # type: ignore[arg-type]
        settings=TenantSettings(),  # type: ignore[arg-type]
    )
    machine_repo = FakeMachineRepo(machines)
    pool_repo = FakePoolRepo(pools or [])
    calendar_repo = FakeCalendarRepo()
    settings_repo = FakeSettingsRepo(
        AdminProductionSettings(
            id=1,
            production_order_number_format="PO-{seq:04d}",
            default_weekly_hours=DEFAULT_WEEKLY_HOURS,
            default_external_lead_days=3,
            response_time_days=response_time_days,
            require_qa=False,
        )
    )
    resolved_uow = uow if uow is not None else FakeUnitOfWork()
    recompute = RecomputeMachineSchedule(
        repos,
        machine_repo,
        calendar_repo,
        settings_repo,
        pool_repo,
        uow=resolved_uow,  # type: ignore[arg-type]
        generation_counter=generation_counter,  # type: ignore[arg-type]
        recompute_lock=recompute_lock,  # type: ignore[arg-type]
    )
    return recompute, order_repo, resolved_uow


# ══════════════════════════════════════════════════════════════════════
# (a) pool order floats onto a member machine's own queue without
#     overlapping it, without the winning member ever landing on the
#     order itself.
# ══════════════════════════════════════════════════════════════════════


async def test_floating_pool_order_placed_after_member_machine_queue_no_overlap():
    machine1 = make_machine(1)
    pool = make_pool(100, machine_ids=[1])
    lot_a = make_lot(1)
    lot_b = make_lot(2)
    order_a = make_order(1, lot_id=1, machine_id=1, duration_minutes=60, queue_sequence=1)
    order_b = make_order(2, lot_id=2, machine_pool_id=100, duration_minutes=30, queue_sequence=1)

    recompute, order_repo, _uow = build_recompute(
        [lot_a, lot_b], [order_a, order_b], [machine1], [pool]
    )
    result = await recompute.execute_all()

    scheduled_a = result.by_machine[1][0]
    scheduled_b = result.by_pool[100][0]
    assert scheduled_a.planned_start is not None
    assert scheduled_a.planned_end is not None
    assert scheduled_b.planned_start is not None
    assert scheduled_b.planned_end is not None
    # No overlap: the pool order's trial on machine 1 must start no
    # earlier than the machine-assigned order's own commitment ends.
    assert scheduled_b.planned_start >= scheduled_a.planned_end
    assert scheduled_b.trial_machine_id == 1
    # trial_machine_id is informational only; never written onto the
    # order's own machine_id (scheduling.forward_walk._merge_pool_queues).
    assert order_repo.orders[2].machine_id is None


# ══════════════════════════════════════════════════════════════════════
# (b) one execute_all() persists dates for both queues, and the pinned/
#     non-pinned planned_by_id attribution rule holds.
# ══════════════════════════════════════════════════════════════════════


async def test_execute_all_persists_dates_and_preserves_planned_by_id_rule():
    machine1 = make_machine(1)
    machine2 = make_machine(2)
    pool = make_pool(100, machine_ids=[1])
    lot_a = make_lot(1)
    lot_b = make_lot(2)
    lot_c = make_lot(3)

    order_a = make_order(1, lot_id=1, machine_id=1, duration_minutes=60, queue_sequence=1)
    order_a.planned_by_id = 55  # a stale attribution the recompute must clear

    order_b = make_order(2, lot_id=2, machine_pool_id=100, duration_minutes=30, queue_sequence=1)

    pinned_start = datetime(2026, 1, 5, 8, 0, tzinfo=UTC)
    pinned_end = datetime(2026, 1, 5, 9, 0, tzinfo=UTC)
    order_c = make_order(
        3,
        lot_id=3,
        machine_id=2,
        duration_minutes=45,
        queue_sequence=1,
        pinned=True,
        planned_start=pinned_start,
        planned_end=pinned_end,
    )
    order_c.planned_by_id = 77  # a planner's own manual override

    recompute, order_repo, _uow = build_recompute(
        [lot_a, lot_b, lot_c], [order_a, order_b, order_c], [machine1, machine2], [pool]
    )
    await recompute.execute_all()

    assert order_repo.orders[1].planned_start is not None
    assert order_repo.orders[1].planned_end is not None
    assert order_repo.orders[1].planned_by_id is None  # non-pinned -> reads as "Auto-planner"

    assert order_repo.orders[2].planned_start is not None
    assert order_repo.orders[2].planned_end is not None
    assert order_repo.orders[2].planned_by_id is None

    # Pinned: window AND attribution both untouched by the recompute.
    assert order_repo.orders[3].planned_start == pinned_start
    assert order_repo.orders[3].planned_end == pinned_end
    assert order_repo.orders[3].planned_by_id == 77


# ══════════════════════════════════════════════════════════════════════
# (d) an order left on a since-deleted machine is still walked.
# ══════════════════════════════════════════════════════════════════════


async def test_order_on_machine_missing_from_machine_repo_is_still_walked():
    """delete_machine.py soft-deletes a machine without reassigning its
    orders; IProductionMachineRepository.get_by_id/get_all both filter
    deleted=False in the real adapter, so a soft-deleted machine's id
    resolves to nothing at all, yet get_all_non_terminal() still surfaces
    a live order still sitting on it. `machines=[]` here stands in for
    that: machine id 5 is absent from the machine repo entirely."""
    lot = make_lot(1)
    order = make_order(1, lot_id=1, machine_id=5, duration_minutes=45, queue_sequence=1)

    recompute, order_repo, _uow = build_recompute([lot], [order], machines=[])
    result = await recompute.execute_all()

    scheduled = result.by_machine[5][0]
    assert scheduled.planned_start is not None
    assert scheduled.planned_end is not None
    assert order_repo.orders[1].planned_start is not None
    assert order_repo.orders[1].planned_end is not None


# ══════════════════════════════════════════════════════════════════════
# (e) an unresolvable pool degrades exactly like
#     schedule_unassigned_orders' pool branch.
# ══════════════════════════════════════════════════════════════════════


async def test_unresolvable_pool_degrades_without_no_machine_assigned_flag():
    lot = make_lot(1)
    order = make_order(1, lot_id=1, machine_pool_id=999, duration_minutes=30, queue_sequence=1)

    recompute, order_repo, _uow = build_recompute([lot], [order], machines=[], pools=[])
    result = await recompute.execute_all()

    scheduled = result.by_pool[999][0]
    assert scheduled.planned_start is None
    assert scheduled.planned_end is None
    # A pool-assigned order reflects a deliberate planner decision,
    # not a bare absence of one; never flagged NO_MACHINE_ASSIGNED even
    # once its pool can no longer be resolved.
    assert ScheduleConflictReason.NO_MACHINE_ASSIGNED.value not in scheduled.conflicts
    assert order_repo.orders[1].planned_start is None
    assert order_repo.orders[1].planned_end is None


# ══════════════════════════════════════════════════════════════════════
# (f) exactly one commit per execute_all() call.
# ══════════════════════════════════════════════════════════════════════


async def test_execute_all_ends_its_reads_and_writes_in_one_commit():
    machine1 = make_machine(1)
    pool = make_pool(100, machine_ids=[1])
    lot_a = make_lot(1)
    lot_b = make_lot(2)
    order_a = make_order(1, lot_id=1, machine_id=1, duration_minutes=60, queue_sequence=1)
    order_b = make_order(2, lot_id=2, machine_pool_id=100, duration_minutes=30, queue_sequence=1)

    uow = CountingUnitOfWork()
    recompute, _order_repo, _uow = build_recompute(
        [lot_a, lot_b], [order_a, order_b], [machine1], [pool], uow=uow
    )
    await recompute.execute_all()

    assert uow.commit_calls == 2


# ══════════════════════════════════════════════════════════════════════
# (g) a sequence-1 order whose raw material has neither arrived nor has a
#     delivery forecast is persisted with no dates (scheduling.
#     is_unplannable_for_missing_material via advance_machine_queue).
# ══════════════════════════════════════════════════════════════════════


async def test_missing_material_order_is_persisted_with_no_dates():
    machine1 = make_machine(1)
    lot = make_lot(1, material_arrived=False)
    order = make_order(1, lot_id=1, machine_id=1, duration_minutes=60, queue_sequence=1)
    order.planned_start = datetime(2026, 1, 1, 8, 0, tzinfo=UTC)  # stale, must be cleared
    order.planned_end = datetime(2026, 1, 1, 9, 0, tzinfo=UTC)

    recompute, order_repo, _uow = build_recompute([lot], [order], [machine1])
    result = await recompute.execute_all()

    scheduled = result.by_machine[1][0]
    assert scheduled.planned_start is None
    assert scheduled.planned_end is None
    assert ScheduleConflictReason.WAITING_ON_MATERIAL.value in scheduled.conflicts
    assert order_repo.orders[1].planned_start is None
    assert order_repo.orders[1].planned_end is None


# ══════════════════════════════════════════════════════════════════════
# Coalescing: (a) skip when a concurrent walk already covers this call's
# own generation.
# ══════════════════════════════════════════════════════════════════════


async def test_execute_all_coalesces_when_generation_already_processed():
    machine1 = make_machine(1)
    lot = make_lot(1)
    order = make_order(1, lot_id=1, machine_id=1, duration_minutes=60, queue_sequence=1)

    # increment_generation() will return 1 (0 -> 1); pre-seeding processed
    # at 1 simulates a concurrent walker that already covered it, e.g. one
    # that queued for the lock behind this call and finished first.
    counter = FakeGenerationCounter(initial_processed=1)
    lock = FakeRecomputeLock()
    uow = CountingUnitOfWork()
    recompute, order_repo, _uow = build_recompute(
        [lot], [order], [machine1], uow=uow, generation_counter=counter, recompute_lock=lock
    )

    result = await recompute.execute_all()

    # The walk never ran: no commit, the order's dates are untouched, and
    # the result is the same empty shape a "nothing to walk" call returns.
    assert uow.commit_calls == 0
    assert order_repo.orders[1].planned_start is None
    assert result.by_machine == {}
    assert result.by_pool == {}
    assert result.manual == []
    assert result.unassigned == []
    # The lock was still taken and released; coalescing happens UNDER the
    # lock, not by racing past it.
    assert lock.enter_count == 1
    assert lock.exit_count == 1


# ══════════════════════════════════════════════════════════════════════
# Coalescing: (b) walk-and-record-processed when this call's generation
# is NOT already covered.
# ══════════════════════════════════════════════════════════════════════


async def test_execute_all_walks_and_records_processed_generation_when_behind():
    machine1 = make_machine(1)
    lot = make_lot(1)
    order = make_order(1, lot_id=1, machine_id=1, duration_minutes=60, queue_sequence=1)

    counter = FakeGenerationCounter()  # starts at generation=0, processed=0
    lock = FakeRecomputeLock()
    uow = CountingUnitOfWork()
    recompute, order_repo, _uow = build_recompute(
        [lot], [order], [machine1], uow=uow, generation_counter=counter, recompute_lock=lock
    )

    result = await recompute.execute_all()

    assert uow.commit_calls == 2
    assert order_repo.orders[1].planned_start is not None
    assert result.by_machine[1][0].planned_start is not None
    # The walk's own generation (1, from this call's own
    # increment_generation()) is what ends up recorded as processed.
    assert counter.processed == 1
    assert lock.enter_count == 1
    assert lock.exit_count == 1


class _CounterThatAdvancesBeforeCurrentGenerationIsSampled(FakeGenerationCounter):
    """Simulates a second caller's own increment_generation() landing while
    this call is queued for the lock: bumps the shared counter as a side
    effect of processed_generation(), the call this implementation makes
    right after acquiring the lock, right before sampling
    current_generation()."""

    async def processed_generation(self) -> int:
        result = await super().processed_generation()
        self._generation += 1  # a concurrent caller's own increment_generation()
        return result


async def test_execute_all_records_a_higher_processed_generation_when_it_advanced_under_the_lock():
    """current_generation() is sampled again, fresh, once this call holds
    the lock; if another mutation's own execute_all() call incremented the
    shared counter while this one was queued for the lock, the generation
    recorded as processed must cover that one too, not just this call's
    own my_generation."""
    machine1 = make_machine(1)
    lot = make_lot(1)
    order = make_order(1, lot_id=1, machine_id=1, duration_minutes=60, queue_sequence=1)

    counter = _CounterThatAdvancesBeforeCurrentGenerationIsSampled()
    lock = FakeRecomputeLock()
    recompute, _order_repo, _uow = build_recompute(
        [lot], [order], [machine1], generation_counter=counter, recompute_lock=lock
    )

    await recompute.execute_all()

    # my_generation was 1 (this call's own increment_generation()), but the
    # counter advanced to 2 before current_generation() was sampled. The
    # HIGHER value is what gets recorded as processed, not the caller's own
    # my_generation.
    assert counter.processed == 2


# ══════════════════════════════════════════════════════════════════════
# Coalescing: (c) fail-open when the coordinator is unavailable.
# ══════════════════════════════════════════════════════════════════════


async def test_execute_all_fails_open_and_walks_unconditionally_when_increment_fails():
    machine1 = make_machine(1)
    lot = make_lot(1)
    order = make_order(1, lot_id=1, machine_id=1, duration_minutes=60, queue_sequence=1)

    counter = FakeGenerationCounter(raise_on=frozenset({"increment_generation"}))
    lock = FakeRecomputeLock()
    uow = CountingUnitOfWork()
    recompute, order_repo, _uow = build_recompute(
        [lot], [order], [machine1], uow=uow, generation_counter=counter, recompute_lock=lock
    )

    result = await recompute.execute_all()

    # The walk still ran unconditionally even though the coordinator itself
    # is broken, and it held the lock, which never depends on Redis, so two
    # walks never run at once.
    assert uow.commit_calls == 2
    assert order_repo.orders[1].planned_start is not None
    assert result.by_machine[1][0].planned_start is not None
    assert lock.enter_count == 1


async def test_execute_all_fails_open_when_processed_generation_read_fails():
    machine1 = make_machine(1)
    lot = make_lot(1)
    order = make_order(1, lot_id=1, machine_id=1, duration_minutes=60, queue_sequence=1)

    counter = FakeGenerationCounter(raise_on=frozenset({"processed_generation"}))
    lock = FakeRecomputeLock()
    uow = CountingUnitOfWork()
    recompute, order_repo, _uow = build_recompute(
        [lot], [order], [machine1], uow=uow, generation_counter=counter, recompute_lock=lock
    )

    result = await recompute.execute_all()

    # Unable to tell whether this generation is already covered, so the
    # safe choice is to walk rather than risk wrongly skipping it. The
    # walk still runs and still commits, under the (successfully acquired)
    # lock.
    assert uow.commit_calls == 2
    assert order_repo.orders[1].planned_start is not None
    assert result.by_machine[1][0].planned_start is not None
    assert lock.enter_count == 1
    assert lock.exit_count == 1


async def test_execute_all_does_not_raise_when_mark_processed_fails():
    machine1 = make_machine(1)
    lot = make_lot(1)
    order = make_order(1, lot_id=1, machine_id=1, duration_minutes=60, queue_sequence=1)

    counter = FakeGenerationCounter(raise_on=frozenset({"mark_processed"}))
    lock = FakeRecomputeLock()
    uow = CountingUnitOfWork()
    recompute, order_repo, _uow = build_recompute(
        [lot], [order], [machine1], uow=uow, generation_counter=counter, recompute_lock=lock
    )

    # A failure recording the completed generation must not undo or hide an
    # already-successful, already-committed walk.
    result = await recompute.execute_all()

    assert uow.commit_calls == 2
    assert order_repo.orders[1].planned_start is not None
    assert result.by_machine[1][0].planned_start is not None
    # Never updated; the walk succeeded, only recording it failed.
    assert counter.processed == 0


# ══════════════════════════════════════════════════════════════════════
# Coalescing: (d) the exact call/sampling order the module docstring's
# correctness argument depends on.
# ══════════════════════════════════════════════════════════════════════


async def test_execute_all_call_order_increments_then_checks_processed_then_samples_current():
    machine1 = make_machine(1)
    lot = make_lot(1)
    order = make_order(1, lot_id=1, machine_id=1, duration_minutes=60, queue_sequence=1)

    counter = FakeGenerationCounter()
    lock = FakeRecomputeLock()
    recompute, _order_repo, _uow = build_recompute(
        [lot], [order], [machine1], generation_counter=counter, recompute_lock=lock
    )

    await recompute.execute_all()

    # increment_generation() happens first (before the lock is even taken);
    # processed_generation() only after the lock is held; current_generation()
    # sampled fresh right before the walk starts reading orders; mark_processed()
    # only after the walk (and its commit) has completed.
    assert counter.calls == [
        "increment_generation",
        "processed_generation",
        "current_generation",
        "mark_processed",
    ]
