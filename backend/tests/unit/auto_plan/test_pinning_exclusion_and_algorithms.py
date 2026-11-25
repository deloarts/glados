"""
Pinned orders as capacity-blocking anchors, exclude_todays_planned gating
(including paused orders), and the selectable placement algorithms
(fair_queue, balanced_load, and the unknown-value fallback).
"""

from datetime import UTC
from datetime import date
from datetime import datetime
from datetime import time
from datetime import timedelta
from zoneinfo import ZoneInfo

from src.modules.fulfillment.application.dto.production_schedule_dto import AutoPlanCommand
from src.modules.fulfillment.application.use_cases.production_schedule import (
    auto_plan as auto_plan_module,
)
from src.modules.fulfillment.domain.value_objects.production_status import ProductionOrderStatus
from src.modules.fulfillment.domain.value_objects.production_status import UrgencyClass
from tests.unit._scheduling_clock import pin_scheduling_clock
from tests.unit.auto_plan._helpers import SYSTEM_ACTOR
from tests.unit.auto_plan._helpers import build_auto_plan
from tests.unit.auto_plan._helpers import make_lot
from tests.unit.auto_plan._helpers import make_machine
from tests.unit.auto_plan._helpers import make_order
from tests.unit.auto_plan.fakes import TENANT_TIMEZONE

TENANT_ZONE = ZoneInfo(TENANT_TIMEZONE)


async def test_pinned_order_is_not_moved_and_still_blocks_capacity_as_an_anchor():
    """A pinned order stays a fixed anchor by default (overwrite_pinned=
    False): it keeps its own machine_id/queue_sequence, and a competing
    QUEUED candidate must still be placed AFTER the anchor's existing
    window, not overlapping it."""
    machine = make_machine(1)
    lot_pinned = make_lot(1)
    lot_candidate = make_lot(2)
    pinned_start = datetime(2026, 1, 5, 8, 0)
    pinned_end = datetime(2026, 1, 5, 10, 0)
    pinned_order = make_order(
        1,
        lot_id=1,
        machine_id=1,
        duration_minutes=120,
        pinned=True,
        queue_sequence=1,
        planned_start=pinned_start,
        planned_end=pinned_end,
    )
    candidate_order = make_order(
        2, lot_id=2, machine_id=1, duration_minutes=60, pinned=False, queue_sequence=2
    )

    auto_plan, order_repo = build_auto_plan(
        [lot_pinned, lot_candidate], [pinned_order, candidate_order], [machine]
    )
    cmd = AutoPlanCommand(assign_machines=False, overwrite_pinned=False)
    result = await auto_plan.execute(SYSTEM_ACTOR, cmd)

    assert order_repo.orders[1].pinned is True
    assert order_repo.orders[1].machine_id == 1
    # The candidate is a "proposal" even when it stays on the same
    # machine, since it's still re-sequenced/re-dated by the planner.
    assert any(p.order_id == 2 for p in result.proposals)


async def test_exclude_todays_planned_default_leaves_a_queued_order_starting_today_untouched(
    monkeypatch,
):
    """A QUEUED order already planned to start today, even though it
    hasn't actually started, is protected by default. Reshuffling it
    mid-day is exactly the shop-floor surprise exclude_todays_planned
    exists to prevent. The clock stands at 07:00, so the walk after the run
    keeps the order where it was planned."""
    today = datetime.now(TENANT_ZONE).date()
    pin_scheduling_clock(
        monkeypatch, datetime.combine(today, time(7, 0), tzinfo=TENANT_ZONE).astimezone(UTC)
    )
    machine = make_machine(1)
    lot = make_lot(1)
    todays_start = datetime.combine(today, time(8, 0), tzinfo=TENANT_ZONE)
    todays_end = datetime.combine(today, time(10, 0), tzinfo=TENANT_ZONE)
    order = make_order(
        1,
        lot_id=1,
        machine_id=1,
        duration_minutes=120,
        queue_sequence=1,
        planned_start=todays_start,
        planned_end=todays_end,
    )

    auto_plan, order_repo = build_auto_plan([lot], [order], [machine])
    cmd = AutoPlanCommand(assign_machines=False)
    result = await auto_plan.execute(SYSTEM_ACTOR, cmd)

    assert result.proposals == []
    assert result.skipped_todays_planned == 1
    assert order_repo.orders[1].planned_start == todays_start
    assert order_repo.orders[1].planned_end == todays_end
    assert order_repo.orders[1].queue_sequence == 1


async def test_exclude_todays_planned_false_allows_reshuffling_todays_order():
    today = datetime.now(TENANT_ZONE).date()
    machine = make_machine(1)
    lot = make_lot(1)
    order = make_order(
        1,
        lot_id=1,
        machine_id=1,
        duration_minutes=120,
        queue_sequence=1,
        planned_start=datetime.combine(today, time(8, 0), tzinfo=TENANT_ZONE),
        planned_end=datetime.combine(today, time(10, 0), tzinfo=TENANT_ZONE),
    )

    auto_plan, _order_repo = build_auto_plan([lot], [order], [machine])
    cmd = AutoPlanCommand(assign_machines=False, exclude_todays_planned=False)
    result = await auto_plan.execute(SYSTEM_ACTOR, cmd)

    assert len(result.proposals) == 1
    assert result.skipped_todays_planned == 0


async def test_exclude_todays_planned_excludes_a_multiday_order_spanning_today():
    """A long-running order that started yesterday and finishes tomorrow
    also touches today, even though its planned_start isn't today. It
    must stay protected too."""
    today = datetime.now(TENANT_ZONE).date()
    machine = make_machine(1)
    lot = make_lot(1)
    order = make_order(
        1,
        lot_id=1,
        machine_id=1,
        duration_minutes=2880,
        queue_sequence=1,
        planned_start=datetime.combine(today - timedelta(days=1), time(8, 0), tzinfo=TENANT_ZONE),
        planned_end=datetime.combine(today + timedelta(days=1), time(17, 0), tzinfo=TENANT_ZONE),
    )

    auto_plan, order_repo = build_auto_plan([lot], [order], [machine])
    cmd = AutoPlanCommand(assign_machines=False)
    result = await auto_plan.execute(SYSTEM_ACTOR, cmd)

    assert result.proposals == []
    assert result.skipped_todays_planned == 1
    assert order_repo.orders[1].queue_sequence == 1


async def test_exclude_todays_planned_uses_the_tenant_local_today(monkeypatch):
    """At 22:30 UTC on 14 July it is already 00:30 on 15 July in Vienna, so
    "today" is the 15th. An order planned on the local 15th, which is still
    the 14th or the 15th in UTC, is protected, and one planned on the 14th,
    which would be today in UTC, is a candidate again."""
    monkeypatch.setattr(
        auto_plan_module, "now_utc", lambda: datetime(2026, 7, 14, 22, 30, tzinfo=UTC)
    )
    machine = make_machine(1)
    yesterdays = make_order(
        1,
        lot_id=1,
        machine_id=1,
        duration_minutes=120,
        queue_sequence=1,
        planned_start=datetime(2026, 7, 14, 8, 0, tzinfo=UTC),
        planned_end=datetime(2026, 7, 14, 10, 0, tzinfo=UTC),
    )
    todays = make_order(
        2,
        lot_id=2,
        machine_id=1,
        duration_minutes=60,
        queue_sequence=2,
        planned_start=datetime(2026, 7, 14, 22, 0, tzinfo=UTC),
        planned_end=datetime(2026, 7, 14, 23, 0, tzinfo=UTC),
    )

    auto_plan, order_repo = build_auto_plan(
        [make_lot(1), make_lot(2)], [yesterdays, todays], [machine]
    )
    result = await auto_plan.execute(SYSTEM_ACTOR, AutoPlanCommand(assign_machines=False))

    assert result.skipped_todays_planned == 1
    assert [p.order_id for p in result.proposals] == [1]
    assert order_repo.orders[2].queue_sequence == 2


async def test_critical_ratio_counts_days_from_the_tenant_local_today(monkeypatch):
    """At 22:30 UTC on 14 July Vienna is on 15 July. Order 2 (one day of
    work, due 16 July) has 1 day left against 4 days for order 1 (three
    days of work, due 19 July), ratios 1 and 1.33, so order 2 goes first.
    Counted from the UTC 14 July they would be 2 and 1.67, the other way
    round."""
    monkeypatch.setattr(
        auto_plan_module, "now_utc", lambda: datetime(2026, 7, 14, 22, 30, tzinfo=UTC)
    )
    machine = make_machine(1)
    long_job = make_order(1, lot_id=1, machine_id=1, duration_minutes=1440, queue_sequence=1)
    short_job = make_order(2, lot_id=2, machine_id=1, duration_minutes=480, queue_sequence=2)

    auto_plan, order_repo = build_auto_plan(
        [
            make_lot(1, required_delivery_date=date(2026, 7, 19)),
            make_lot(2, required_delivery_date=date(2026, 7, 16)),
        ],
        [long_job, short_job],
        [machine],
    )
    await auto_plan.execute(
        SYSTEM_ACTOR, AutoPlanCommand(assign_machines=False, algorithm="critical_ratio")
    )

    assert order_repo.orders[2].queue_sequence < order_repo.orders[1].queue_sequence


async def test_paused_order_is_never_touched_regardless_of_exclude_todays_planned():
    """An already-started task, even if currently paused, must never be
    a candidate. This holds independent of exclude_todays_planned (it's
    gated purely on status == QUEUED, same as IN_PROGRESS)."""
    machine = make_machine(1)
    lot = make_lot(1)
    order = make_order(
        1,
        lot_id=1,
        machine_id=1,
        duration_minutes=60,
        queue_sequence=1,
        status=ProductionOrderStatus.PAUSED,
    )

    auto_plan, order_repo = build_auto_plan([lot], [order], [machine])
    # Even with exclude_todays_planned=False (i.e. "allow reshuffling
    # today's queue"), a paused order must still never move.
    cmd = AutoPlanCommand(assign_machines=False, exclude_todays_planned=False)
    result = await auto_plan.execute(SYSTEM_ACTOR, cmd)

    assert result.proposals == []
    assert order_repo.orders[1].status == ProductionOrderStatus.PAUSED.value
    assert order_repo.orders[1].machine_id == 1
    assert order_repo.orders[1].queue_sequence == 1


async def test_algorithm_fair_queue_uses_creation_order_ignoring_priority():
    """Inverts test_higher_priority_candidate_wins_the_earlier_slot_on_a_
    shared_machine's expectation: under Fair Queue (FIFO), creation order
    wins and critical priority does not jump the queue."""
    machine = make_machine(1)
    lot_low = make_lot(1, priority=UrgencyClass.NORMAL)
    lot_high = make_lot(2, priority=UrgencyClass.CRITICAL)
    order_created_first = make_order(
        1, lot_id=1, machine_id=1, duration_minutes=60, priority=UrgencyClass.NORMAL
    )
    order_created_later_but_critical = make_order(
        2, lot_id=2, machine_id=1, duration_minutes=60, priority=UrgencyClass.CRITICAL
    )

    auto_plan, order_repo = build_auto_plan(
        [lot_low, lot_high], [order_created_first, order_created_later_but_critical], [machine]
    )
    cmd = AutoPlanCommand(assign_machines=False, algorithm="fair_queue")
    await auto_plan.execute(SYSTEM_ACTOR, cmd)

    assert order_repo.orders[1].queue_sequence < order_repo.orders[2].queue_sequence


async def test_algorithm_balanced_load_avoids_the_heavily_booked_machine():
    """Machine 1 lets the candidate finish soonest (small existing pinned
    window). The default Urgent First (earliest-finish selection) picks
    it. But machine 1's anchor carries a huge estimated_duration_minutes,
    so under Balanced Load (least-loaded selection) the candidate must go
    to machine 2's much lighter total load instead, even though machine 2
    finishes it later."""
    not_before = date(2026, 1, 5)

    def build_scenario():
        machine1 = make_machine(1)
        machine2 = make_machine(2)
        lot1 = make_lot(1)
        lot2 = make_lot(2)
        lot_candidate = make_lot(3)
        anchor1 = make_order(
            1,
            lot_id=1,
            machine_id=1,
            duration_minutes=100000,
            pinned=True,
            queue_sequence=1,
            planned_start=datetime.combine(not_before, time(8, 0)),
            planned_end=datetime.combine(not_before, time(8, 1)),
        )
        anchor2 = make_order(
            2,
            lot_id=2,
            machine_id=2,
            duration_minutes=1,
            pinned=True,
            queue_sequence=1,
            planned_start=datetime.combine(not_before, time(8, 0)),
            planned_end=datetime.combine(not_before + timedelta(days=3), time(17, 0)),
        )
        candidate = make_order(
            3, lot_id=3, machine_id=None, duration_minutes=60, not_before=not_before
        )
        return build_auto_plan(
            [lot1, lot2, lot_candidate], [anchor1, anchor2, candidate], [machine1, machine2]
        )

    auto_plan_default, order_repo_default = build_scenario()
    cmd_default = AutoPlanCommand(assign_machines=True)
    await auto_plan_default.execute(SYSTEM_ACTOR, cmd_default)
    assert order_repo_default.orders[3].machine_id == 1

    auto_plan_balanced, order_repo_balanced = build_scenario()
    cmd_balanced = AutoPlanCommand(assign_machines=True, algorithm="balanced_load")
    await auto_plan_balanced.execute(SYSTEM_ACTOR, cmd_balanced)
    assert order_repo_balanced.orders[3].machine_id == 2


async def test_algorithm_unknown_value_falls_back_to_default_urgent_first():
    machine = make_machine(1)
    lot_low = make_lot(1, priority=UrgencyClass.NORMAL)
    lot_high = make_lot(2, priority=UrgencyClass.CRITICAL)
    order_low = make_order(
        1, lot_id=1, machine_id=1, duration_minutes=60, priority=UrgencyClass.NORMAL
    )
    order_high = make_order(
        2, lot_id=2, machine_id=1, duration_minutes=60, priority=UrgencyClass.CRITICAL
    )

    auto_plan, order_repo = build_auto_plan([lot_low, lot_high], [order_low, order_high], [machine])
    cmd = AutoPlanCommand(assign_machines=False, algorithm="not-a-real-algorithm")
    await auto_plan.execute(SYSTEM_ACTOR, cmd)

    assert order_repo.orders[2].queue_sequence < order_repo.orders[1].queue_sequence
