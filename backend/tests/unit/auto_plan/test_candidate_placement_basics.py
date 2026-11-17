"""
AutoPlan's request/command validation, priority ordering and non-overlapping
incremental placement on a shared machine, the direct match against a
from-scratch machine queue walk, assign_machines gating, and the
unknown-material/no-capable-machine skip reporting.
"""

import itertools
from datetime import UTC
from datetime import date
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest
from pydantic import ValidationError

from src.modules.fulfillment.adapters.inbound.api.schemas.production_schedule_schema import (
    AutoPlanRequest,
)
from src.modules.fulfillment.application.dto.production_schedule_dto import AutoPlanCommand
from src.modules.fulfillment.domain.services.scheduling import build_machine_calendar
from src.modules.fulfillment.domain.value_objects.auto_plan_skip_reason import AutoPlanSkipReason
from src.modules.fulfillment.domain.value_objects.production_status import UrgencyClass
from tests.unit._scheduling_clock import pin_scheduling_clock
from tests.unit.auto_plan._helpers import DEFAULT_WEEKLY_HOURS
from tests.unit.auto_plan._helpers import SYSTEM_ACTOR
from tests.unit.auto_plan._helpers import build_auto_plan
from tests.unit.auto_plan._helpers import make_lot
from tests.unit.auto_plan._helpers import make_machine
from tests.unit.auto_plan._helpers import make_order
from tests.unit.auto_plan.fakes import TENANT_TIMEZONE
from tests.unit.scheduling_service._helpers import walk_machine_queue

# The walk plans no queued order before now, and the fixtures are dated in
# January 2026.
_BEFORE_THE_FIXTURES = datetime(2026, 1, 1, tzinfo=UTC)


def test_auto_plan_request_rejects_the_legacy_assign_pool_machines_field():
    """assign_pool_machines is not a request field (planning_level is), so
    a stale client sending that bool must get a validation error, not
    have it silently ignored. Silently accepting
    it would leave a stale client thinking it got the re-sequence-only
    pool behavior it asked for, when the request actually just defaulted
    to planning_level='machines' underneath it."""
    with pytest.raises(ValidationError):
        AutoPlanRequest(assign_pool_machines=False)


def test_auto_plan_request_planning_level_defaults_to_machines():
    assert AutoPlanRequest().planning_level == "machines"


def test_auto_plan_command_planning_level_defaults_to_machines():
    assert AutoPlanCommand().planning_level == "machines"


async def test_higher_priority_candidate_wins_the_earlier_slot_on_a_shared_machine():
    """Two QUEUED orders on the same already-assigned machine, competing
    only by priority (no due date): CRITICAL must be placed before
    NORMAL regardless of order id / creation order."""
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
    cmd = AutoPlanCommand(assign_machines=False)
    await auto_plan.execute(SYSTEM_ACTOR, cmd)

    assert order_repo.orders[2].queue_sequence < order_repo.orders[1].queue_sequence


async def test_candidates_on_the_same_machine_never_overlap():
    """Three candidates piled onto one machine must be placed
    back-to-back, never overlapping: the direct correctness check for
    the cursor-based incremental placement."""
    machine = make_machine(1)
    lots = [make_lot(i) for i in (1, 2, 3)]
    orders = [
        make_order(i, lot_id=i, machine_id=1, duration_minutes=120, priority=UrgencyClass.NORMAL)
        for i in (1, 2, 3)
    ]

    auto_plan, order_repo = build_auto_plan(lots, orders, [machine])
    cmd = AutoPlanCommand(assign_machines=False)
    await auto_plan.execute(SYSTEM_ACTOR, cmd)

    placed = sorted(order_repo.orders.values(), key=lambda o: o.queue_sequence)
    for earlier, later in itertools.pairwise(placed):
        assert earlier.planned_end is not None
        assert later.planned_start is not None
        assert earlier.planned_end <= later.planned_start


async def test_matches_a_from_scratch_machine_queue_walk(monkeypatch):
    """The optimized cursor-based placement must produce byte-identical
    dates to calling walk_machine_queue once over the final queue;
    if the incremental math and the ground-truth full walk ever drift
    apart, this catches it."""
    pin_scheduling_clock(monkeypatch, _BEFORE_THE_FIXTURES)
    # not_before fixes the earliest floor to a deterministic date, and the
    # pinned clock stands before it, so both walks floor every queued order
    # at the same moment and the exact-timestamp comparison is stable.
    fixed_not_before = date(2026, 1, 5)
    machine = make_machine(1)
    lots = [make_lot(i) for i in range(1, 6)]
    orders = [
        make_order(
            i,
            lot_id=i,
            machine_id=1,
            duration_minutes=90,
            priority=UrgencyClass.NORMAL,
            not_before=fixed_not_before,
        )
        for i in range(1, 6)
    ]

    auto_plan, order_repo = build_auto_plan(lots, orders, [machine])
    cmd = AutoPlanCommand(assign_machines=False)
    await auto_plan.execute(SYSTEM_ACTOR, cmd)

    calendar = build_machine_calendar(
        DEFAULT_WEEKLY_HOURS, None, {}, zone=ZoneInfo(TENANT_TIMEZONE)
    )
    now = _BEFORE_THE_FIXTURES
    from src.modules.fulfillment.application.services.scheduling_context import build_contexts

    repos = auto_plan._repos  # reaching in for a ground-truth re-walk
    final_orders = list(order_repo.orders.values())
    contexts = await build_contexts(final_orders, repos, machine=machine, zone=UTC)
    ground_truth = {
        s.order_id: (s.planned_start, s.planned_end)
        for s in walk_machine_queue(contexts, calendar, now)
    }

    for order in final_orders:
        assert (order.planned_start, order.planned_end) == ground_truth[order.id]


async def test_assign_machines_false_leaves_unassigned_order_untouched():
    machine = make_machine(1)
    lot = make_lot(1)
    order = make_order(1, lot_id=1, machine_id=None, duration_minutes=60)

    auto_plan, order_repo = build_auto_plan([lot], [order], [machine])
    cmd = AutoPlanCommand(assign_machines=False)
    result = await auto_plan.execute(SYSTEM_ACTOR, cmd)

    assert result.proposals == []
    assert order_repo.orders[1].machine_id is None


async def test_assign_machines_true_assigns_an_unassigned_order():
    machine = make_machine(1)
    lot = make_lot(1)
    order = make_order(1, lot_id=1, machine_id=None, duration_minutes=60)

    auto_plan, order_repo = build_auto_plan([lot], [order], [machine])
    cmd = AutoPlanCommand(assign_machines=True)
    result = await auto_plan.execute(SYSTEM_ACTOR, cmd)

    assert len(result.proposals) == 1
    assert order_repo.orders[1].machine_id == 1


# ── Skipped candidates (waiting_on_material / no_eligible_machine) ──────


async def test_candidate_with_unknown_material_is_skipped_and_reported():
    """A sequence-1 INTERNAL order whose raw material has neither arrived
    nor has a delivery forecast (make_lot's material_arrived=False) is
    never assigned a machine/queue position: scheduling.
    is_unplannable_for_missing_material would return None dates on every
    trial regardless, so _place_candidates skips it before ever resolving
    a machine, and reports it in result.skipped with WAITING_ON_MATERIAL
    instead of silently leaving a bare no-op."""
    machine = make_machine(1)
    lot = make_lot(1, material_arrived=False)
    order = make_order(1, lot_id=1, machine_id=1, duration_minutes=60, queue_sequence=1)

    auto_plan, order_repo = build_auto_plan([lot], [order], [machine])
    result = await auto_plan.execute(SYSTEM_ACTOR, AutoPlanCommand())

    assert result.proposals == []
    # Restored to its real pre-run value, never left at the temporary
    # negative placeholder _seed_anchors shifts every candidate to.
    assert order_repo.orders[1].queue_sequence == 1
    assert order_repo.orders[1].machine_id == 1
    assert len(result.skipped) == 1
    assert result.skipped[0].order_id == 1
    assert result.skipped[0].production_order_number == order.production_order_number
    assert result.skipped[0].reason == AutoPlanSkipReason.WAITING_ON_MATERIAL.value


async def test_candidate_with_no_capable_machine_is_skipped_and_reported():
    """The order is already on machine 1, but machine 1 doesn't cover the
    position's required fabrication method: resolve_eligible_machine_ids'
    rule 3 (re-sequence only within the machine it's already on) returns
    [] since that machine does not qualify, reported as skipped with
    NO_ELIGIBLE_MACHINE rather than a bare no-op."""
    machine = make_machine(1, fabrication_method_ids=[999])  # doesn't cover method 1
    lot = make_lot(1)
    order = make_order(1, lot_id=1, machine_id=1, duration_minutes=60, queue_sequence=1)

    auto_plan, order_repo = build_auto_plan([lot], [order], [machine])
    result = await auto_plan.execute(SYSTEM_ACTOR, AutoPlanCommand())

    assert result.proposals == []
    assert order_repo.orders[1].queue_sequence == 1
    assert len(result.skipped) == 1
    assert result.skipped[0].order_id == 1
    assert result.skipped[0].reason == AutoPlanSkipReason.NO_ELIGIBLE_MACHINE.value


class _FailingWalk:
    async def execute_all(self, **_kwargs):
        raise RuntimeError("walk failed")


async def test_a_failed_walk_after_the_plan_still_answers_with_the_plan():
    """The plan is committed before the walk runs, so a walk that fails
    leaves the answer as it is, with the orders as planned."""
    machine = make_machine(1)
    orders = [make_order(1, lot_id=1, machine_id=1, duration_minutes=60)]
    auto_plan, _ = build_auto_plan([make_lot(1)], orders, [machine])
    auto_plan._recompute = _FailingWalk()

    result = await auto_plan.execute(SYSTEM_ACTOR, AutoPlanCommand(assign_machines=False))

    assert [p.order_id for p in result.proposals] == [1]
