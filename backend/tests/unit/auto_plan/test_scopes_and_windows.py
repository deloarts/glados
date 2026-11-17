"""
What Auto-Plan writes besides its placements: an order it places loses its
old planned window, so the walk places it at its new slot even inside the
frozen window; a candidate it cannot place keeps its queue place when no
placement went into that queue, also for a pool that has been archived; and
a run that places nothing changes no queue.
"""

from dataclasses import replace
from datetime import UTC
from datetime import datetime
from datetime import timedelta

import pytest

from src.modules.fulfillment.application.dto.production_schedule_dto import AutoPlanCommand
from src.modules.platform.domain.exceptions import ConcurrentModificationError
from tests.unit._scheduling_clock import pin_scheduling_clock
from tests.unit.auto_plan._helpers import SYSTEM_ACTOR
from tests.unit.auto_plan._helpers import build_auto_plan
from tests.unit.auto_plan._helpers import make_lot
from tests.unit.auto_plan._helpers import make_machine
from tests.unit.auto_plan._helpers import make_order
from tests.unit.auto_plan._helpers import make_pool

_NOW = datetime(2026, 1, 5, 6, tzinfo=UTC)


@pytest.mark.parametrize("level", ["machines", "pools"])
async def test_an_order_of_an_archived_pool_keeps_its_place(monkeypatch, level) -> None:
    pin_scheduling_clock(monkeypatch, _NOW)
    machine = make_machine(1, fabrication_method_ids=[2])
    pool = replace(make_pool(7, [1]), archived=True)
    order = make_order(1, 1, machine_pool_id=7, queue_sequence=4)
    auto_plan, repo = build_auto_plan([make_lot(1)], [order], [machine], pools=[pool])

    await auto_plan.execute(SYSTEM_ACTOR, AutoPlanCommand(planning_level=level))

    assert repo.orders[1].queue_sequence == 4
    assert repo.orders[1].machine_pool_id == 7


async def test_a_run_that_places_nothing_changes_no_queue(monkeypatch) -> None:
    pin_scheduling_clock(monkeypatch, _NOW)
    capable_of_nothing = make_machine(1, fabrication_method_ids=[2])
    orders = [
        make_order(1, 1, machine_id=1, queue_sequence=5),
        make_order(2, 2, machine_id=1, queue_sequence=9),
    ]
    auto_plan, repo = build_auto_plan([make_lot(1), make_lot(2)], orders, [capable_of_nothing])

    await auto_plan.execute(SYSTEM_ACTOR, AutoPlanCommand(planning_level="machines"))

    assert [repo.orders[i].queue_sequence for i in (1, 2)] == [5, 9]


async def test_a_placed_order_loses_its_old_planned_window(monkeypatch) -> None:
    pin_scheduling_clock(monkeypatch, _NOW)
    start = _NOW + timedelta(hours=26)
    order = make_order(
        1,
        1,
        machine_id=1,
        planned_start=start,
        planned_end=start + timedelta(hours=1),
        queue_sequence=1,
    )
    auto_plan, repo = build_auto_plan([make_lot(1)], [order], [make_machine(1)])
    settings = auto_plan._settings  # type: ignore[attr-defined]
    settings.settings = replace(settings.settings, frozen_window_hours=48)

    await auto_plan.execute(SYSTEM_ACTOR, AutoPlanCommand(planning_level="machines"))

    placed = repo.orders[1]
    assert placed.machine_id == 1
    assert (placed.planned_start, placed.planned_end) != (start, start + timedelta(hours=1))


async def test_a_machine_archived_while_the_run_waits_for_its_queue_stops_the_run(
    monkeypatch,
) -> None:
    """The run reads its machines before it locks their queues, and an
    archive takes a machine's queue lock before it counts the machine's
    orders. A machine archived in between is noticed under the lock, and the
    run stops instead of queueing orders on it."""
    pin_scheduling_clock(monkeypatch, _NOW)
    machine = make_machine(1, fabrication_method_ids=[2])
    order = make_order(1, 1, queue_sequence=3)
    auto_plan, repo = build_auto_plan([make_lot(1)], [order], [machine])

    async def archive_meanwhile(machine_id, machine_pool_id=None) -> None:
        if machine_id == 1:
            machine.archived = True

    monkeypatch.setattr(repo, "lock_queue_scope", archive_meanwhile)

    with pytest.raises(ConcurrentModificationError, match="archived"):
        await auto_plan.execute(SYSTEM_ACTOR, AutoPlanCommand(planning_level="machines"))
    assert repo.orders[1].machine_id is None
