"""
Every Auto-Plan run walks the schedule once after its write, also a run that
moves nothing, so the dates are current when the answer arrives. The
progress counts that walk, 0/1 before and 1/1 after it, and a walk that
fails is logged while the answer stays the plan.
"""

from src.modules.fulfillment.application.dto.production_schedule_dto import AutoPlanCommand
from src.modules.fulfillment.application.dto.production_schedule_dto import AutoPlanProgress
from tests.unit.auto_plan._helpers import SYSTEM_ACTOR
from tests.unit.auto_plan._helpers import build_auto_plan
from tests.unit.auto_plan._helpers import make_machine


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
