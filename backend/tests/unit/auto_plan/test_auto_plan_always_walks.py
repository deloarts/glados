"""
Every Auto-Plan run walks the schedule once after its write, also a run that
moves nothing, so the dates are current when the answer arrives. The
progress counts that walk, 0/1 before and 1/1 after it, a walk that fails is
logged while the answer stays the plan, and the result lists the orders the
walk moved to another day.
"""

from datetime import UTC
from datetime import datetime
from datetime import timedelta

from src.modules.fulfillment.application.dto.production_schedule_dto import AutoPlanCommand
from src.modules.fulfillment.application.dto.production_schedule_dto import AutoPlanProgress
from tests.unit._scheduling_clock import pin_scheduling_clock
from tests.unit.auto_plan._helpers import SYSTEM_ACTOR
from tests.unit.auto_plan._helpers import build_auto_plan
from tests.unit.auto_plan._helpers import make_lot
from tests.unit.auto_plan._helpers import make_machine
from tests.unit.auto_plan._helpers import make_manual_lot
from tests.unit.auto_plan._helpers import make_order


def _count_walks(auto_plan, *, fail: bool = False) -> list[int]:
    """Counts the walks the run requests by wrapping its recompute."""
    calls: list[int] = []
    walk = auto_plan._recompute.execute_all

    async def counted(*args, **kwargs):
        calls.append(1)
        if fail:
            raise RuntimeError("walk failed")
        return await walk(*args, **kwargs)

    auto_plan._recompute.execute_all = counted
    return calls


async def test_a_run_that_moves_nothing_still_walks_once():
    auto_plan, _orders = build_auto_plan([], [], [make_machine(1)])
    calls = _count_walks(auto_plan)
    events: list[AutoPlanProgress] = []

    result = await auto_plan.execute(SYSTEM_ACTOR, AutoPlanCommand(), progress=events.append)

    assert result.proposals == []
    assert calls == [1]
    recomputing = [(e.current, e.total) for e in events if e.stage == "recomputing"]
    assert recomputing == [(0, 1), (1, 1)]


async def test_a_failed_walk_is_logged_and_the_plan_still_answers(glados_caplog):
    auto_plan, _orders = build_auto_plan([], [], [make_machine(1)])
    calls = _count_walks(auto_plan, fail=True)

    result = await auto_plan.execute(SYSTEM_ACTOR, AutoPlanCommand())

    assert calls == [1]
    assert result.proposals == []
    assert any("Schedule recompute failed" in r.getMessage() for r in glados_caplog.records)


async def test_the_result_lists_the_orders_the_walk_moved_to_another_day(monkeypatch):
    """A manual step dated weeks out with nothing holding it back: the run
    has nothing to place, its walk dates the step today, and the result lists
    it with the reason and its column. An order the walk keeps on its day is
    only counted."""
    now = datetime(2026, 1, 5, 7, 0, tzinfo=UTC)
    pin_scheduling_clock(monkeypatch, now)
    stale = datetime(2026, 1, 26, 8, 0, tzinfo=UTC)
    manual = make_order(1, lot_id=1, planned_start=stale, planned_end=stale + timedelta(hours=1))
    kept = make_order(
        2,
        lot_id=2,
        machine_id=1,
        pinned=True,
        planned_start=datetime(2026, 1, 6, 7, 0, tzinfo=UTC),
        planned_end=datetime(2026, 1, 6, 8, 0, tzinfo=UTC),
    )
    auto_plan, _orders = build_auto_plan(
        [make_manual_lot(1), make_lot(2)], [manual, kept], [make_machine(1)]
    )

    result = await auto_plan.execute(SYSTEM_ACTOR, AutoPlanCommand())

    assert result.walk_failed is False
    [row] = result.redated
    assert row.order_id == 1
    assert row.column == "manual"
    assert row.before_planned_start == stale
    assert row.after_planned_start is not None
    assert row.after_planned_start.date() == now.date()
    assert row.reason is not None
    assert row.reason.kind == "ready_now"
    assert result.kept_day == 1


async def test_a_failed_walk_lists_nothing_and_says_so():
    auto_plan, _orders = build_auto_plan([], [], [make_machine(1)])
    _count_walks(auto_plan, fail=True)

    result = await auto_plan.execute(SYSTEM_ACTOR, AutoPlanCommand())

    assert result.walk_failed is True
    assert result.redated == []
