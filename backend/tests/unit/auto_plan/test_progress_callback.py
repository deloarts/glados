"""
AutoPlan's live progress callback (SSE): the exact stage sequence, placed-
vs-skipped candidate flags at both the machines and pools levels, and that
a raising callback never alters the planning result.
"""

from datetime import date

from src.modules.fulfillment.application.dto.production_schedule_dto import AutoPlanCommand
from src.modules.fulfillment.application.dto.production_schedule_dto import AutoPlanProgress
from src.modules.fulfillment.application.dto.production_schedule_dto import AutoPlanProgressOrder
from src.modules.fulfillment.application.use_cases.production_schedule.auto_plan import AutoPlan
from src.modules.fulfillment.domain.value_objects.auto_plan_skip_reason import AutoPlanSkipReason
from src.modules.fulfillment.domain.value_objects.production_status import UrgencyClass
from tests.unit.auto_plan._helpers import SYSTEM_ACTOR
from tests.unit.auto_plan._helpers import build_auto_plan
from tests.unit.auto_plan._helpers import make_lot
from tests.unit.auto_plan._helpers import make_machine
from tests.unit.auto_plan._helpers import make_manual_lot
from tests.unit.auto_plan._helpers import make_order
from tests.unit.auto_plan._helpers import make_pool
from tests.unit.auto_plan.fakes import FakeOrderRepo

# ══════════════════════════════════════════════════════════════════════
# Live progress (SSE): the stages and counts AutoPlan reports through
# its progress callback.
# ══════════════════════════════════════════════════════════════════════


async def test_progress_callback_receives_the_exact_stage_sequence():
    """Three candidates, already on the same machine (assign_machines=
    False, rule 3 'stick to current machine' places all three, no
    skips), so touched_machine_ids ends up as the single-element {1} and
    both the placing and recomputing stages have a small, exactly-known
    total. Confirms the full stage sequence from the emission-points
    table, the per-candidate event count, that totals stay constant
    within a stage, and that `current` strictly increases within a
    stage."""
    machine = make_machine(1)
    lots = [make_lot(i) for i in (1, 2, 3)]
    orders = [
        make_order(i, lot_id=i, machine_id=1, duration_minutes=60, priority=UrgencyClass.NORMAL)
        for i in (1, 2, 3)
    ]

    auto_plan, _ = build_auto_plan(lots, orders, [machine])
    events: list[AutoPlanProgress] = []
    cmd = AutoPlanCommand(assign_machines=False)
    await auto_plan.execute(SYSTEM_ACTOR, cmd, progress=events.append)

    assert [e.stage for e in events] == [
        "preparing",
        "loading_orders",
        "scoring",
        "placing",
        "placing",
        "placing",
        "placing",
        "recomputing",
        "recomputing",
        "finalizing",
    ]

    placing_events = [e for e in events if e.stage == "placing"]
    assert [e.total for e in placing_events] == [3, 3, 3, 3]
    assert [e.current for e in placing_events] == [0, 1, 2, 3]

    per_candidate_events = [e for e in placing_events if e.order is not None]
    assert len(per_candidate_events) == 3
    assert {e.order.order_id for e in per_candidate_events} == {1, 2, 3}
    assert all(e.order.placed for e in per_candidate_events)
    assert all(e.order.after_machine_id == 1 for e in per_candidate_events)

    recomputing_events = [e for e in events if e.stage == "recomputing"]
    assert [e.total for e in recomputing_events] == [1, 1]
    assert [e.current for e in recomputing_events] == [0, 1]

    preparing_scoring_events = [
        e for e in events if e.stage in ("preparing", "loading_orders", "scoring")
    ]
    assert all(
        e.current is None and e.total is None and e.order is None for e in preparing_scoring_events
    )

    finalizing_event = next(e for e in events if e.stage == "finalizing")
    assert finalizing_event.current is None
    assert finalizing_event.total is None
    assert finalizing_event.order is None


async def test_progress_events_flag_placed_vs_skipped_candidates_at_machines_level():
    """A candidate with no eligible machine (its step needs fabrication
    method 2; the only candidate machine covers method 1) emits
    placed=False with unchanged before/after machine and pool ids; a
    placed candidate in the same run carries the correct
    after_machine_id."""
    machine = make_machine(1, fabrication_method_ids=[1])
    lot_placed = make_lot(1)
    lot_skipped = make_lot(2)
    lot_skipped.positions[0].steps[0].fabrication_method_id = 2
    order_placed = make_order(1, lot_id=1, machine_id=None, duration_minutes=60)
    order_skipped = make_order(2, lot_id=2, machine_id=None, duration_minutes=60)

    auto_plan, _ = build_auto_plan(
        [lot_placed, lot_skipped], [order_placed, order_skipped], [machine]
    )
    events: list[AutoPlanProgress] = []
    cmd = AutoPlanCommand(assign_machines=True)
    await auto_plan.execute(SYSTEM_ACTOR, cmd, progress=events.append)

    by_order_id = {
        e.order.order_id: e.order for e in events if e.stage == "placing" and e.order is not None
    }
    assert set(by_order_id) == {1, 2}

    placed = by_order_id[1]
    assert placed.placed is True
    assert placed.after_machine_id == 1

    skipped = by_order_id[2]
    assert skipped.placed is False
    assert skipped.before_machine_id == skipped.after_machine_id
    assert skipped.before_machine_pool_id == skipped.after_machine_pool_id
    assert skipped.after_machine_id is None  # never touched: unassigned going in and coming out


async def test_progress_event_for_a_placed_pool_candidate_carries_after_machine_pool_id():
    """Pools-level twin of the machines-level placed check above,
    mirrors test_pools_level_pool_only_order_is_reassigned_only_among_
    eligible_pools' scenario (pool 10 doesn't cover the required
    fabrication method, pool 20 does)."""
    machine1 = make_machine(1, fabrication_method_ids=[9])  # doesn't cover method 1
    machine2 = make_machine(2, fabrication_method_ids=[1])  # covers method 1
    pool_a = make_pool(10, machine_ids=[1])
    pool_b = make_pool(20, machine_ids=[2])
    lot = make_lot(1)
    order = make_order(1, lot_id=1, machine_id=None, machine_pool_id=10, duration_minutes=60)

    auto_plan, _ = build_auto_plan([lot], [order], [machine1, machine2], [pool_a, pool_b])
    events: list[AutoPlanProgress] = []
    cmd = AutoPlanCommand(planning_level="pools")
    await auto_plan.execute(SYSTEM_ACTOR, cmd, progress=events.append)

    candidate_events = [e.order for e in events if e.stage == "placing" and e.order is not None]
    assert len(candidate_events) == 1
    order_event = candidate_events[0]
    assert order_event.placed is True
    assert order_event.before_machine_pool_id == 10
    assert order_event.after_machine_pool_id == 20
    assert order_event.before_machine_id is None
    assert order_event.after_machine_id is None


async def test_raising_progress_callback_does_not_alter_the_result():
    """A callback that raises on every call must never break or
    alter a planning run: the result (and every order's final state) is
    identical to the same fixture run with progress=None. not_before
    pins every candidate's earliest floor to a deterministic date (see
    test_matches_a_from_scratch_machine_queue_walk's comment)
    so the two independent execute() calls' own now() samples, a few
    microseconds apart, can't make an exact comparison flaky."""
    fixed_not_before = date(2030, 1, 7)

    def build_scenario() -> tuple[AutoPlan, FakeOrderRepo]:
        machine = make_machine(1)
        lots = [make_lot(i) for i in (1, 2, 3)]
        orders = [
            make_order(
                i,
                lot_id=i,
                machine_id=1,
                duration_minutes=120,
                priority=UrgencyClass.NORMAL,
                not_before=fixed_not_before,
            )
            for i in (1, 2, 3)
        ]
        return build_auto_plan(lots, orders, [machine])

    auto_plan_plain, repo_plain = build_scenario()
    result_plain = await auto_plan_plain.execute(
        SYSTEM_ACTOR, AutoPlanCommand(assign_machines=False)
    )

    auto_plan_raising, repo_raising = build_scenario()

    def raising_callback(event: AutoPlanProgress) -> None:
        raise RuntimeError("boom")

    result_raising = await auto_plan_raising.execute(
        SYSTEM_ACTOR, AutoPlanCommand(assign_machines=False), progress=raising_callback
    )

    assert result_raising == result_plain
    # public_id (Entity base) is a random uuid4() per construction, so
    # compare the fields the planner itself actually writes rather than
    # full dataclass equality.
    for order_id in repo_plain.orders:
        plain_order = repo_plain.orders[order_id]
        raising_order = repo_raising.orders[order_id]
        assert raising_order.machine_id == plain_order.machine_id
        assert raising_order.machine_pool_id == plain_order.machine_pool_id
        assert raising_order.queue_sequence == plain_order.queue_sequence
        assert raising_order.planned_start == plain_order.planned_start
        assert raising_order.planned_end == plain_order.planned_end
        assert raising_order.pinned == plain_order.pinned


async def test_progress_defaults_to_none_and_behaves_identically_to_explicit_none():
    """Sanity, cheap: execute()'s progress parameter defaults to None,
    producing the exact same result as passing progress=None explicitly
    on the same fixture."""
    fixed_not_before = date(2030, 1, 7)

    def build_scenario() -> tuple[AutoPlan, FakeOrderRepo]:
        machine = make_machine(1)
        lot = make_lot(1)
        order = make_order(
            1, lot_id=1, machine_id=1, duration_minutes=60, not_before=fixed_not_before
        )
        return build_auto_plan([lot], [order], [machine])

    auto_plan_default, repo_default = build_scenario()
    result_default = await auto_plan_default.execute(
        SYSTEM_ACTOR, AutoPlanCommand(assign_machines=False)
    )

    auto_plan_explicit, repo_explicit = build_scenario()
    result_explicit = await auto_plan_explicit.execute(
        SYSTEM_ACTOR, AutoPlanCommand(assign_machines=False), progress=None
    )

    assert result_default == result_explicit
    # public_id (Entity base) is a random uuid4() per construction, so
    # compare the fields the planner itself actually writes rather than
    # full dataclass equality.
    default_order = repo_default.orders[1]
    explicit_order = repo_explicit.orders[1]
    assert default_order.machine_id == explicit_order.machine_id
    assert default_order.queue_sequence == explicit_order.queue_sequence
    assert default_order.planned_start == explicit_order.planned_start
    assert default_order.planned_end == explicit_order.planned_end


def _candidate_events(events: list[AutoPlanProgress]) -> dict[int, AutoPlanProgressOrder]:
    return {e.order.order_id: e.order for e in events if e.stage == "placing" and e.order}


async def test_a_manual_step_without_a_machine_is_neither_streamed_nor_reported():
    """A manual step has no machine decision, so the stream leaves it out
    just as the result does, and the placing total counts only the orders
    the stream reports."""
    machine = make_machine(1)
    lots = [make_lot(1), make_manual_lot(2)]
    orders = [
        make_order(1, lot_id=1, machine_id=None, duration_minutes=60),
        make_order(2, lot_id=2, machine_id=None, duration_minutes=60),
    ]

    auto_plan, _ = build_auto_plan(lots, orders, [machine])
    events: list[AutoPlanProgress] = []
    result = await auto_plan.execute(
        SYSTEM_ACTOR, AutoPlanCommand(assign_machines=True), progress=events.append
    )

    assert set(_candidate_events(events)) == {1}
    assert {e.total for e in events if e.stage == "placing"} == {1}
    assert [p.order_id for p in result.proposals] == [1]
    assert result.skipped == []


async def test_a_run_on_some_machines_leaves_other_teams_unassigned_orders_alone():
    """Order 2's work only machine 2 can do, and the run covers machine 1
    alone, so the order is no candidate of this run: it is neither
    streamed nor reported and keeps its queue. Order 3's work no machine
    can do, so it stays in and is reported skipped, its event carrying the
    reason the result gives."""
    machines = [
        make_machine(1, fabrication_method_ids=[1]),
        make_machine(2, fabrication_method_ids=[2]),
    ]
    lots = [make_lot(1), make_lot(2), make_lot(3)]
    lots[1].positions[0].steps[0].fabrication_method_id = 2
    lots[2].positions[0].steps[0].fabrication_method_id = 3
    orders = [make_order(i, lot_id=i, machine_id=None, duration_minutes=60) for i in (1, 2, 3)]

    auto_plan, order_repo = build_auto_plan(lots, orders, machines)
    events: list[AutoPlanProgress] = []
    result = await auto_plan.execute(
        SYSTEM_ACTOR,
        AutoPlanCommand(assign_machines=True, machine_ids=[1]),
        progress=events.append,
    )

    streamed = _candidate_events(events)
    assert set(streamed) == {1, 3}
    assert [p.order_id for p in result.proposals] == [1]
    assert [(s.order_id, s.reason) for s in result.skipped] == [
        (3, AutoPlanSkipReason.NO_ELIGIBLE_MACHINE.value)
    ]
    assert streamed[3].placed is False
    assert streamed[3].reason == AutoPlanSkipReason.NO_ELIGIBLE_MACHINE.value
    assert order_repo.orders[2].machine_id is None


async def test_every_skipped_event_carries_the_reason_of_the_result():
    """Each unplaced event names the reason the result files the order
    under, so the dialog never shows a skip without one."""
    machine = make_machine(1, fabrication_method_ids=[1])
    lots = [make_lot(1), make_lot(2), make_manual_lot(3)]
    lots[1].positions[0].steps[0].fabrication_method_id = 2
    orders = [make_order(i, lot_id=i, machine_id=None, duration_minutes=60) for i in (1, 2, 3)]

    auto_plan, _ = build_auto_plan(lots, orders, [machine])
    events: list[AutoPlanProgress] = []
    result = await auto_plan.execute(
        SYSTEM_ACTOR, AutoPlanCommand(assign_machines=True), progress=events.append
    )

    unplaced = {i: o.reason for i, o in _candidate_events(events).items() if not o.placed}
    assert unplaced == {s.order_id: s.reason for s in result.skipped}
    assert all(reason for reason in unplaced.values())


async def test_the_log_counts_only_orders_whose_placement_changed(glados_caplog):
    """A second run over a plan the first run made places the order where
    it already runs, in the same window, so it is a proposal but no
    move."""
    fixed_not_before = date(2030, 1, 7)
    machine = make_machine(1)
    order = make_order(
        1, lot_id=1, machine_id=None, duration_minutes=60, not_before=fixed_not_before
    )
    auto_plan, _ = build_auto_plan([make_lot(1)], [order], [machine])
    cmd = AutoPlanCommand(assign_machines=True)

    first = await auto_plan.execute(SYSTEM_ACTOR, cmd)
    glados_caplog.clear()
    second = await auto_plan.execute(SYSTEM_ACTOR, cmd)

    assert [p.order_id for p in first.proposals] == [1]
    assert [p.order_id for p in second.proposals] == [1]
    summaries = [r.getMessage() for r in glados_caplog.records if "auto-planner" in r.getMessage()]
    assert len(summaries) == 1
    assert "0 order(s) moved" in summaries[0]
