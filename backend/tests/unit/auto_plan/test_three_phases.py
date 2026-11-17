"""
Auto-Plan reads in a transaction it ends before the placement, places
without holding a lock, and only then locks its queues and the orders it
may move. A queue whose orders changed between the read and the write keeps
its state, and its placements are reported as changed while planning. A
lost race while writing is written once more on the server.
"""

from dataclasses import replace
from datetime import UTC
from datetime import datetime
from types import SimpleNamespace

import pytest

from src.modules.fulfillment.application.dto.production_schedule_dto import AutoPlanCommand
from src.modules.fulfillment.application.dto.production_schedule_dto import AutoPlanProgress
from src.modules.fulfillment.domain.value_objects.auto_plan_skip_reason import AutoPlanSkipReason
from src.modules.fulfillment.domain.value_objects.production_status import ProductionOrderStatus
from src.modules.platform.adapters.outbound.persistence.lost_race import lost_race
from tests.unit._scheduling_clock import pin_scheduling_clock
from tests.unit.auto_plan._helpers import SYSTEM_ACTOR
from tests.unit.auto_plan._helpers import build_auto_plan
from tests.unit.auto_plan._helpers import make_lot
from tests.unit.auto_plan._helpers import make_machine
from tests.unit.auto_plan._helpers import make_order

_NOW = datetime(2026, 1, 5, 6, tzinfo=UTC)


class _DriverError(Exception):
    def __init__(self, sqlstate: str) -> None:
        super().__init__(sqlstate)
        self.sqlstate = sqlstate


def _database_error(sqlstate: str) -> Exception:
    error = Exception(f"SQLSTATE {sqlstate}")
    error.orig = _DriverError(sqlstate)  # type: ignore[attr-defined]
    return error


def _two_machines_one_order_each():
    machines = [make_machine(1), make_machine(2)]
    orders = [
        make_order(1, 1, machine_id=1, queue_sequence=3),
        make_order(2, 2, machine_id=2, queue_sequence=7),
    ]
    return build_auto_plan([make_lot(1), make_lot(2)], orders, machines)


def _record(auto_plan, repo, log: list[str]) -> None:
    """Records the commits, the locks and the placement in the order they
    happen."""
    uow = auto_plan._uow
    commit, rollback = uow.commit, uow.rollback
    lock_queue_scope, lock_for_update = repo.lock_queue_scope, repo.lock_for_update
    place_all = auto_plan._place_all

    async def recording_commit() -> None:
        log.append("commit")
        await commit()

    async def recording_rollback() -> None:
        log.append("rollback")
        await rollback()

    async def recording_lock_queue_scope(machine_id, machine_pool_id=None) -> None:
        log.append("lock")
        await lock_queue_scope(machine_id, machine_pool_id)

    async def recording_lock_for_update(ids) -> None:
        log.append("lock")
        await lock_for_update(ids)

    def recording_place_all(*args) -> None:
        log.append("place")
        place_all(*args)

    uow.commit, uow.rollback = recording_commit, recording_rollback
    repo.lock_queue_scope, repo.lock_for_update = (
        recording_lock_queue_scope,
        recording_lock_for_update,
    )
    auto_plan._place_all = recording_place_all


async def test_no_lock_is_held_while_the_run_places(monkeypatch) -> None:
    pin_scheduling_clock(monkeypatch, _NOW)
    auto_plan, repo = _two_machines_one_order_each()
    log: list[str] = []
    _record(auto_plan, repo, log)

    await auto_plan.execute(
        SYSTEM_ACTOR, AutoPlanCommand(planning_level="machines", assign_machines=False)
    )

    place = log.index("place")
    assert "lock" not in log[:place]
    # The read transaction ends before the placement, the write one after it.
    assert log[place - 1] == "commit"
    assert "lock" in log[place:]
    assert log[-1] == "commit"


async def test_a_queue_that_changed_while_planning_is_left_alone_and_reported(
    monkeypatch,
) -> None:
    pin_scheduling_clock(monkeypatch, _NOW)
    auto_plan, repo = _two_machines_one_order_each()
    place_all = auto_plan._place_all

    def start_order_one_meanwhile(*args) -> None:
        place_all(*args)
        repo.orders[1] = replace(
            repo.orders[1],
            status=ProductionOrderStatus.IN_PROGRESS,
            actual_start=_NOW,
        )

    auto_plan._place_all = start_order_one_meanwhile

    result = await auto_plan.execute(
        SYSTEM_ACTOR, AutoPlanCommand(planning_level="machines", assign_machines=False)
    )

    assert repo.orders[1].status == ProductionOrderStatus.IN_PROGRESS.value
    assert repo.orders[1].queue_sequence == 3
    assert [(s.order_id, s.reason) for s in result.skipped] == [
        (1, AutoPlanSkipReason.CHANGED_WHILE_PLANNING.value)
    ]
    # The other machine's queue did not change, so its placement is written.
    assert [p.order_id for p in result.proposals] == [2]
    assert repo.orders[2].queue_sequence == 1


async def test_the_stream_ends_as_the_result_for_a_placement_the_write_dropped(
    monkeypatch,
) -> None:
    """The order was streamed as placed while placing; the write dropped its
    placement, so a later event reports it unplaced, in its own queue."""
    pin_scheduling_clock(monkeypatch, _NOW)
    auto_plan, repo = _two_machines_one_order_each()
    place_all = auto_plan._place_all

    def start_order_one_meanwhile(*args) -> None:
        place_all(*args)
        repo.orders[1] = replace(
            repo.orders[1],
            status=ProductionOrderStatus.IN_PROGRESS,
            actual_start=_NOW,
        )

    auto_plan._place_all = start_order_one_meanwhile
    events: list[AutoPlanProgress] = []

    result = await auto_plan.execute(
        SYSTEM_ACTOR,
        AutoPlanCommand(planning_level="machines", assign_machines=False),
        progress=events.append,
    )

    frames = [e for e in events if e.stage == "placing" and e.order is not None]
    assert [f.order.order_id for f in frames if f.order.placed] == [1, 2]
    last = {f.order.order_id: f.order for f in frames}
    assert {i for i, o in last.items() if o.placed} == {p.order_id for p in result.proposals}
    assert {(i, o.reason) for i, o in last.items() if not o.placed} == {
        (s.order_id, s.reason) for s in result.skipped
    }
    dropped = last[1]
    assert (dropped.before_machine_id, dropped.after_machine_id) == (1, 1)
    # Reported before the walk starts, at the end of the placing count.
    follow_up = events.index(next(f for f in frames if not f.order.placed))
    assert (events[follow_up].current, events[follow_up].total) == (2, 2)
    assert events[follow_up + 1].stage == "recomputing"


async def test_an_order_queued_meanwhile_keeps_its_place_beside_the_plan(monkeypatch) -> None:
    """A placement drawn from the queue's state at the read could take the
    place of an order queued meanwhile; the queue is skipped instead."""
    pin_scheduling_clock(monkeypatch, _NOW)
    auto_plan, repo = _two_machines_one_order_each()
    place_all = auto_plan._place_all

    def queue_a_new_order_meanwhile(*args) -> None:
        place_all(*args)
        repo.orders[9] = make_order(9, 1, machine_id=2, queue_sequence=1)

    auto_plan._place_all = queue_a_new_order_meanwhile

    result = await auto_plan.execute(
        SYSTEM_ACTOR, AutoPlanCommand(planning_level="machines", assign_machines=False)
    )

    assert [(s.order_id, s.reason) for s in result.skipped] == [
        (2, AutoPlanSkipReason.CHANGED_WHILE_PLANNING.value)
    ]
    assert repo.orders[2].queue_sequence == 7
    assert repo.orders[9].queue_sequence == 1


async def test_a_lost_race_while_writing_is_written_once_more(monkeypatch) -> None:
    pin_scheduling_clock(monkeypatch, _NOW)
    auto_plan, repo = _two_machines_one_order_each()
    auto_plan._retryable = lost_race
    monkeypatch.setattr(
        "src.modules.fulfillment.application.use_cases.production_schedule.auto_plan._RETRY_DELAY_SECONDS",
        (0, 0),
    )
    lock_for_update = repo.lock_for_update
    failures = [_database_error("55P03")]

    async def time_out_once(ids) -> None:
        if failures:
            raise failures.pop()
        await lock_for_update(ids)

    repo.lock_for_update = time_out_once
    log: list[str] = []
    _record(auto_plan, repo, log)

    result = await auto_plan.execute(
        SYSTEM_ACTOR, AutoPlanCommand(planning_level="machines", assign_machines=False)
    )

    assert log.count("rollback") == 1
    assert log.count("place") == 1
    assert sorted(p.order_id for p in result.proposals) == [1, 2]


@pytest.mark.parametrize("sqlstate", ["57014", None])
async def test_an_error_that_is_no_lost_race_is_not_written_again(monkeypatch, sqlstate) -> None:
    pin_scheduling_clock(monkeypatch, _NOW)
    auto_plan, repo = _two_machines_one_order_each()
    auto_plan._retryable = lost_race
    error = _database_error(sqlstate) if sqlstate else RuntimeError("broken")
    calls = SimpleNamespace(count=0)

    async def always_fail(orders) -> None:
        calls.count += 1
        raise error

    repo.save_schedule = always_fail

    with pytest.raises(type(error)):
        await auto_plan.execute(
            SYSTEM_ACTOR, AutoPlanCommand(planning_level="machines", assign_machines=False)
        )
    assert calls.count == 1


async def test_a_second_lost_race_is_raised(monkeypatch) -> None:
    pin_scheduling_clock(monkeypatch, _NOW)
    auto_plan, repo = _two_machines_one_order_each()
    auto_plan._retryable = lost_race
    monkeypatch.setattr(
        "src.modules.fulfillment.application.use_cases.production_schedule.auto_plan._RETRY_DELAY_SECONDS",
        (0, 0),
    )
    calls = SimpleNamespace(count=0)

    async def always_deadlock(orders) -> None:
        calls.count += 1
        raise _database_error("40P01")

    repo.save_schedule = always_deadlock

    with pytest.raises(Exception, match="40P01"):
        await auto_plan.execute(
            SYSTEM_ACTOR, AutoPlanCommand(planning_level="machines", assign_machines=False)
        )
    assert calls.count == 2
