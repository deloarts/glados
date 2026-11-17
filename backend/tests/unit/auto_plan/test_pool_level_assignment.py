"""
Pool-level planning: unresolved-order-to-pool-member resolution, machine-
resolved orders as anchors, pool reassignment among eligible pools, and the
QA/fabrication routing rules repeated at the pools planning level.
"""

from datetime import UTC
from datetime import date
from datetime import datetime
from zoneinfo import ZoneInfo

from src.modules.catalogue.domain.value_objects.step_role import StepRole
from src.modules.fulfillment.application.dto.production_schedule_dto import AutoPlanCommand
from src.modules.fulfillment.domain.entities.lot_position import LotPosition
from src.modules.fulfillment.domain.entities.lot_step import LotStep
from src.modules.fulfillment.domain.entities.production_lot import ProductionLot
from src.modules.fulfillment.domain.value_objects.auto_plan_skip_reason import AutoPlanSkipReason
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionKind
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionStatus
from src.modules.fulfillment.domain.value_objects.lot_status import LotStatus
from src.modules.fulfillment.domain.value_objects.production_status import UrgencyClass
from tests.unit._scheduling_clock import pin_scheduling_clock
from tests.unit.auto_plan._helpers import SYSTEM_ACTOR
from tests.unit.auto_plan._helpers import build_auto_plan
from tests.unit.auto_plan._helpers import make_lot
from tests.unit.auto_plan._helpers import make_machine
from tests.unit.auto_plan._helpers import make_order
from tests.unit.auto_plan._helpers import make_pool
from tests.unit.auto_plan.fakes import TENANT_TIMEZONE

# The walk plans no queued order before now, and the fixtures are dated in
# January 2026.
_BEFORE_THE_FIXTURES = datetime(2026, 1, 1, tzinfo=UTC)

# Calendar hours are local to the tenant, 08:00 in its zone.
TENANT_ZONE = ZoneInfo(TENANT_TIMEZONE)


async def test_pool_assigned_unresolved_order_resolves_to_a_pool_member_by_default():
    """planning_level defaults to 'machines', which resolves a pool order
    onto a pool member. Leaving every pool order unresolved (re-sequence
    only) is what planning_level='pools' is for, see the pools-level
    tests below."""
    machines = [make_machine(1), make_machine(2)]
    pool = make_pool(10, machine_ids=[1, 2])
    lot = make_lot(1)
    order = make_order(1, lot_id=1, machine_id=None, machine_pool_id=10, duration_minutes=60)

    auto_plan, order_repo = build_auto_plan([lot], [order], machines, [pool])
    cmd = AutoPlanCommand()  # planning_level defaults to "machines"
    result = await auto_plan.execute(SYSTEM_ACTOR, cmd)

    assert len(result.proposals) == 1
    assert order_repo.orders[1].machine_id in (1, 2)
    assert order_repo.orders[1].machine_pool_id == 10


# ══════════════════════════════════════════════════════════════════════
# planning_level='pools' (pool-first planning)
# ══════════════════════════════════════════════════════════════════════


async def test_pools_level_machine_resolved_order_is_an_anchor_never_moved():
    """A machine-resolved order is an anchor under 'pools', same standing
    as pinned/IN_PROGRESS, even though it's an ordinary QUEUED/unpinned
    order that 'machines' level would happily re-sequence. Planning at
    the pool level never touches it at all, not even a re-sequence within
    its own machine, its dates stay bit-identical to what was already
    there."""
    machine = make_machine(1)
    lot = make_lot(1)
    start = datetime(2026, 1, 5, 8, 0)
    end = datetime(2026, 1, 5, 9, 0)
    order = make_order(
        1,
        lot_id=1,
        machine_id=1,
        duration_minutes=60,
        queue_sequence=3,
        planned_start=start,
        planned_end=end,
    )

    auto_plan, order_repo = build_auto_plan([lot], [order], [machine])
    cmd = AutoPlanCommand(planning_level="pools")
    result = await auto_plan.execute(SYSTEM_ACTOR, cmd)

    assert result.proposals == []
    assert order_repo.orders[1].machine_id == 1
    assert order_repo.orders[1].queue_sequence == 3
    assert order_repo.orders[1].planned_start == start
    assert order_repo.orders[1].planned_end == end


async def test_pools_level_pool_only_order_is_reassigned_only_among_eligible_pools():
    """Pool 10 (machine 1) doesn't cover the position's required
    fabrication method, pool 20 (machine 2) does. The order must move
    to pool 20, never fall back to "stay on the current pool" the way
    resolve_eligible_machine_ids' rule 3 sticks to the current machine."""
    machine1 = make_machine(1, fabrication_method_ids=[9])  # doesn't cover method 1
    machine2 = make_machine(2, fabrication_method_ids=[1])  # covers method 1
    pool_a = make_pool(10, machine_ids=[1])
    pool_b = make_pool(20, machine_ids=[2])
    lot = make_lot(1)
    order = make_order(1, lot_id=1, machine_id=None, machine_pool_id=10, duration_minutes=60)

    auto_plan, order_repo = build_auto_plan([lot], [order], [machine1, machine2], [pool_a, pool_b])
    cmd = AutoPlanCommand(planning_level="pools")
    result = await auto_plan.execute(SYSTEM_ACTOR, cmd)

    assert order_repo.orders[1].machine_id is None
    assert order_repo.orders[1].machine_pool_id == 20
    assert len(result.proposals) == 1
    diff = result.proposals[0]
    assert diff.before_machine_pool_id == 10
    assert diff.after_machine_pool_id == 20
    assert diff.before_machine_id is None
    assert diff.after_machine_id is None


async def test_pools_level_truly_unassigned_order_gains_an_eligible_pool_with_real_dates(
    monkeypatch,
):
    """Drains the no-machine-no-pool board column: a truly-
    unassigned machine-requiring order gains a pool (pool-scoped
    queue_sequence starting at 1) and real dates, computed by
    RecomputeMachineSchedule.execute_all()'s pool-queue walk
    (schedule_all's pool merge). AutoPlan itself never writes machine_id, only
    machine_pool_id."""
    pin_scheduling_clock(monkeypatch, _BEFORE_THE_FIXTURES)
    fixed_not_before = date(2026, 1, 5)  # a Monday
    machine = make_machine(1, fabrication_method_ids=[1])
    pool = make_pool(10, machine_ids=[1])
    lot = make_lot(1)
    order = make_order(
        1,
        lot_id=1,
        machine_id=None,
        machine_pool_id=None,
        duration_minutes=60,
        not_before=fixed_not_before,
    )

    auto_plan, order_repo = build_auto_plan([lot], [order], [machine], [pool])
    cmd = AutoPlanCommand(planning_level="pools")
    result = await auto_plan.execute(SYSTEM_ACTOR, cmd)

    assert len(result.proposals) == 1
    assert order_repo.orders[1].machine_id is None
    assert order_repo.orders[1].machine_pool_id == 10
    assert order_repo.orders[1].queue_sequence == 1
    assert order_repo.orders[1].planned_start == datetime(2026, 1, 5, 8, 0, tzinfo=TENANT_ZONE)
    assert order_repo.orders[1].planned_end == datetime(2026, 1, 5, 9, 0, tzinfo=TENANT_ZONE)


async def test_pools_level_truly_unassigned_order_with_no_eligible_pool_is_left_untouched():
    machine = make_machine(1, fabrication_method_ids=[9])  # doesn't cover method 1
    pool = make_pool(10, machine_ids=[1])
    lot = make_lot(1)
    order = make_order(1, lot_id=1, machine_id=None, machine_pool_id=None, duration_minutes=60)

    auto_plan, order_repo = build_auto_plan([lot], [order], [machine], [pool])
    cmd = AutoPlanCommand(planning_level="pools")
    result = await auto_plan.execute(SYSTEM_ACTOR, cmd)

    assert result.proposals == []
    assert order_repo.orders[1].machine_id is None
    assert order_repo.orders[1].machine_pool_id is None
    assert len(result.skipped) == 1
    assert result.skipped[0].reason == AutoPlanSkipReason.NO_ELIGIBLE_POOL.value


async def test_pools_level_order_whose_eligible_pools_have_no_member_in_run_is_left_out():
    """Pool 10's only member, machine 1, covers the required method, but
    the run is limited to machine 2. The order is another team's work,
    so the run neither moves nor reports it, as the machines level does
    with an order only machines outside the run could take."""
    machine1 = make_machine(1, fabrication_method_ids=[1])  # covers method 1, but out of scope
    machine2 = make_machine(2, fabrication_method_ids=[1])  # in scope, not a pool member
    pool = make_pool(10, machine_ids=[1])
    lot = make_lot(1)
    order = make_order(1, lot_id=1, machine_id=None, machine_pool_id=10, duration_minutes=60)

    auto_plan, order_repo = build_auto_plan([lot], [order], [machine1, machine2], [pool])
    cmd = AutoPlanCommand(planning_level="pools", machine_ids=[2])
    result = await auto_plan.execute(SYSTEM_ACTOR, cmd)

    assert result.proposals == []
    assert result.skipped == []
    assert order_repo.orders[1].machine_pool_id == 10


async def test_pools_level_order_with_no_eligible_pool_anywhere_is_still_reported():
    """A run limited to some machines still reports an order that no pool
    at all could take, since no other run would place it either."""
    machine1 = make_machine(1, fabrication_method_ids=[2])
    machine2 = make_machine(2, fabrication_method_ids=[1])
    pool = make_pool(10, machine_ids=[1])
    lot = make_lot(1)
    order = make_order(1, lot_id=1, machine_id=None, machine_pool_id=10, duration_minutes=60)

    auto_plan, _ = build_auto_plan([lot], [order], [machine1, machine2], [pool])
    cmd = AutoPlanCommand(planning_level="pools", machine_ids=[2])
    result = await auto_plan.execute(SYSTEM_ACTOR, cmd)

    assert [skip.reason for skip in result.skipped] == [AutoPlanSkipReason.NO_ELIGIBLE_POOL.value]


async def test_pools_level_unassigned_inspection_order_stays_machine_and_pool_less():
    """Rule 1b (unassigned QA -> never auto-assigned) applies identically
    under 'pools': an unassigned QA order stays exactly as unassigned as
    it started, never landing on a pool (assert_pool_capability_match
    would reject that anyway) NOR on an otherwise-eligible-looking QA
    machine present in the run."""
    machines = [
        make_machine(1, fabrication_method_ids=[7]),  # plain fabrication machine
        make_machine(2, is_qa_machine=True),
    ]
    pool = make_pool(10, machine_ids=[1])
    lot = ProductionLot(
        id=1,
        created=date(2026, 1, 1),
        changed=None,
        changes=[],
        lot_number="LOT-0001",
        quantity=10.0,
        status=LotStatus.PLANNED,
        priority=UrgencyClass.NORMAL,
        note=None,
        creator_id=1,
        made_item_id=1,
        project_id=1,
        input_demand_id=None,
        required_delivery_date=None,
    )
    position = LotPosition(
        id=1,
        created=date(2026, 1, 1),
        changed=None,
        changes=[],
        sequence=1,
        kind=LotPositionKind.INTERNAL,
        status=LotPositionStatus.ORDERED_OR_QUEUED,
        quantity=10.0,
        quantity_completed=0.0,
        note=None,
        creator_id=1,
        lot_id=1,
        steps=[
            LotStep(
                id=1,
                created=date(2026, 1, 1),
                note=None,
                estimated_setup_minutes=0,
                estimated_minutes_per_piece=1.0,
                sequence=1,
                creator_id=1,
                fabrication_method_id=None,
                lot_id=1,
                position_id=1,
                source_process_id=None,
                role=StepRole.INSPECTION,
                inspection_method_id=1,
            )
        ],
    )
    lot.positions = [position]
    order = make_order(1, lot_id=1, machine_id=None, duration_minutes=60)

    auto_plan, order_repo = build_auto_plan([lot], [order], machines, [pool])
    cmd = AutoPlanCommand(planning_level="pools")
    result = await auto_plan.execute(SYSTEM_ACTOR, cmd)

    assert result.proposals == []
    assert order_repo.orders[1].machine_id is None
    assert order_repo.orders[1].machine_pool_id is None


async def test_pools_level_machine_less_qa_order_is_not_reported_skipped_and_gets_dated(
    monkeypatch,
):
    """Pools-level sibling of the 'machines' test above
    (test_machines_level_machine_less_qa_order_is_not_reported_skipped_and_
    gets_dated): the is_manual_step guard sits at the very top of
    _place_candidates' trial loop, before the pools/machines split even
    runs, so it fires identically regardless of planning_level: a
    machine-less QA order must not land in result.skipped here, must not
    gain a pool (QA is never pool-eligible in the first place), and is
    dated by the manual bucket, not a pool queue."""
    pin_scheduling_clock(monkeypatch, _BEFORE_THE_FIXTURES)
    fixed_not_before = date(2026, 1, 5)  # a Monday
    machines = [
        make_machine(1, fabrication_method_ids=[1]),
        make_machine(2, is_qa_machine=True),
    ]
    pool = make_pool(10, machine_ids=[1])
    qa_lot = ProductionLot(
        id=1,
        created=date(2026, 1, 1),
        changed=None,
        changes=[],
        lot_number="LOT-0001",
        quantity=10.0,
        status=LotStatus.PLANNED,
        priority=UrgencyClass.NORMAL,
        note=None,
        creator_id=1,
        made_item_id=1,
        project_id=1,
        input_demand_id=1,
        required_delivery_date=None,
    )
    qa_position = LotPosition(
        id=1,
        created=date(2026, 1, 1),
        changed=None,
        changes=[],
        sequence=1,
        kind=LotPositionKind.INTERNAL,
        status=LotPositionStatus.ORDERED_OR_QUEUED,
        quantity=10.0,
        quantity_completed=0.0,
        note=None,
        creator_id=1,
        lot_id=1,
        steps=[
            LotStep(
                id=1,
                created=date(2026, 1, 1),
                note=None,
                estimated_setup_minutes=0,
                estimated_minutes_per_piece=1.0,
                sequence=1,
                creator_id=1,
                fabrication_method_id=None,
                fabrication_method_requires_machine=False,
                lot_id=1,
                position_id=1,
                source_process_id=None,
                role=StepRole.INSPECTION,
                inspection_method_id=1,
            )
        ],
    )
    qa_lot.positions = [qa_position]
    qa_order = make_order(
        1, lot_id=1, machine_id=None, duration_minutes=60, not_before=fixed_not_before
    )

    # An ordinary pool-eligible fabrication order, included purely to give
    # this run a touched scope (pools mode records a placement's
    # touched_machine_ids entry as None, same as the QA order's own
    # machine_id (see _place_candidates), so len(touched_machine_ids) == 1
    # either way, but a real placement is needed to reach that state at
    # all) so _build_result's total_touched gate actually runs
    # execute_all() and the QA order's planned dates get populated.
    fab_lot = make_lot(2)
    fab_order = make_order(
        2,
        lot_id=2,
        machine_id=None,
        machine_pool_id=10,
        duration_minutes=60,
        not_before=fixed_not_before,
    )

    auto_plan, order_repo = build_auto_plan(
        [qa_lot, fab_lot], [qa_order, fab_order], machines, [pool]
    )
    cmd = AutoPlanCommand(planning_level="pools")
    result = await auto_plan.execute(SYSTEM_ACTOR, cmd)

    assert result.skipped == []
    assert order_repo.orders[1].machine_id is None
    assert order_repo.orders[1].machine_pool_id is None
    assert order_repo.orders[1].planned_start == datetime(2026, 1, 5, 8, 0, tzinfo=TENANT_ZONE)
    assert order_repo.orders[1].planned_end == datetime(2026, 1, 5, 9, 0, tzinfo=TENANT_ZONE)


async def test_pools_level_never_writes_machine_id_on_a_fabrication_order():
    """Combines all three fabrication order shapes in one run: a
    machine-resolved anchor, a pool-only candidate, and a truly-
    unassigned candidate. It confirms none of them ever gains/keeps a
    machine_id except the anchor, which already had one going in. Also
    exercises pool_queue_lengths across two candidates landing in the
    same pool within a single run: they must get distinct, pool-scoped
    queue_sequence values."""
    fixed_not_before = date(2026, 1, 5)
    machine1 = make_machine(1, fabrication_method_ids=[1])
    machine2 = make_machine(2, fabrication_method_ids=[1])
    machine3 = make_machine(3, fabrication_method_ids=[1])
    pool = make_pool(10, machine_ids=[2, 3])
    lot_anchor = make_lot(1)
    lot_pool_candidate = make_lot(2)
    lot_unassigned = make_lot(3)
    anchor_order = make_order(1, lot_id=1, machine_id=1, duration_minutes=60, queue_sequence=1)
    pool_candidate_order = make_order(
        2,
        lot_id=2,
        machine_id=None,
        machine_pool_id=10,
        duration_minutes=60,
        not_before=fixed_not_before,
    )
    unassigned_order = make_order(
        3,
        lot_id=3,
        machine_id=None,
        machine_pool_id=None,
        duration_minutes=60,
        not_before=fixed_not_before,
    )

    auto_plan, order_repo = build_auto_plan(
        [lot_anchor, lot_pool_candidate, lot_unassigned],
        [anchor_order, pool_candidate_order, unassigned_order],
        [machine1, machine2, machine3],
        [pool],
    )
    cmd = AutoPlanCommand(planning_level="pools")
    await auto_plan.execute(SYSTEM_ACTOR, cmd)

    assert order_repo.orders[1].machine_id == 1  # the anchor, unchanged
    assert order_repo.orders[2].machine_id is None
    assert order_repo.orders[2].machine_pool_id == 10
    assert order_repo.orders[3].machine_id is None
    assert order_repo.orders[3].machine_pool_id == 10
    assert {order_repo.orders[2].queue_sequence, order_repo.orders[3].queue_sequence} == {1, 2}
    for order_id, order in order_repo.orders.items():
        if order_id != 1:
            assert order.machine_id is None
