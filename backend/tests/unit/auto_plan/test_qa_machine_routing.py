"""
Inspection orders are assigned only to a QA-capable machine and fabrication
orders never are, at both the machines and machine-less levels.
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
from tests.unit.auto_plan.fakes import TENANT_TIMEZONE

# The walk plans no queued order before now, and the fixtures are dated in
# January 2026.
_BEFORE_THE_FIXTURES = datetime(2026, 1, 1, tzinfo=UTC)

# Calendar hours are local to the tenant, 08:00 in its zone.
TENANT_ZONE = ZoneInfo(TENANT_TIMEZONE)


async def test_inspection_order_is_assigned_only_to_a_qa_machine():
    """An inspection-role LotStep has fabrication_method_id=None (see
    lot_step_model.py's ck_lot_step_role_method), so no fabrication
    capability can gate it; the is_qa_machine flag is the whole
    capability: only a QA/measuring machine is eligible, a plain
    fabrication machine never is (resolve_eligible_machine_ids' QA
    gate). The order already has a machine (create_lot.py's default-
    machine pre-fill, or a person assigning it by hand): an unassigned
    QA order is never auto-assigned at all (rule 1b), so exercising
    the gate itself needs one that already has a machine and falls
    through to rule 2 (assign_machines=True); even considering every
    candidate, it can only ever land back on the QA machine."""
    machines = [
        make_machine(1, fabrication_method_ids=[7]),  # plain fabrication machine
        make_machine(2, is_qa_machine=True),
    ]
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
        # Real (arrived) material, see make_lot's own material_arrived
        # docstring. This test is exercising QA-machine gating, not
        # material timing, and needs a placeable candidate to prove
        # len(result.proposals) == 1 below (FakeLotRepo.
        # get_raw_material_arrived_quantity reports abundant supply for
        # any demand id).
        input_demand_id=1,
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
    order = make_order(1, lot_id=1, machine_id=2, duration_minutes=60)

    auto_plan, order_repo = build_auto_plan([lot], [order], machines)
    cmd = AutoPlanCommand(assign_machines=True)
    result = await auto_plan.execute(SYSTEM_ACTOR, cmd)

    assert len(result.proposals) == 1
    assert order_repo.orders[1].machine_id == 2


async def test_fabrication_order_is_never_assigned_to_a_qa_machine():
    """The QA gate cuts both ways: a dedicated measuring machine must
    never receive fabrication work, even when the only alternative is
    leaving the order unassigned."""
    machine = make_machine(1, is_qa_machine=True, fabrication_method_ids=[1])
    lot = make_lot(1)
    order = make_order(1, lot_id=1, machine_id=None, duration_minutes=60)

    auto_plan, order_repo = build_auto_plan([lot], [order], [machine])
    cmd = AutoPlanCommand(assign_machines=True)
    result = await auto_plan.execute(SYSTEM_ACTOR, cmd)

    assert result.proposals == []
    assert order_repo.orders[1].machine_id is None


async def test_unassigned_inspection_order_stays_machine_less_with_assign_machines_false():
    """A machine on a QA step is opt-in configuration (InspectionMethod.
    default_machine_id), never something Auto-Plan invents, so a
    born-internal QA order (which starts out machine-less, create_lot.py's
    auto-queue path) is not planned onto a capable QA machine regardless of
    assign_machines. The default
    settings (assign_machines=False, planning_level='machines') must leave
    it exactly as machine-less as it started: Auto-Plan is not the path
    that gives it one; create_lot.py's pre-fill (or a person assigning it
    by hand) is."""
    machines = [
        make_machine(1, fabrication_method_ids=[7]),  # plain fabrication machine
        make_machine(2, is_qa_machine=True),
    ]
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
    # machine_id=None, machine_pool_id=None: exactly how create_lot.py's
    # _auto_queue_inspection_position born-internal QA orders start out
    # when their method has no default_machine_id configured.
    order = make_order(1, lot_id=1, machine_id=None, duration_minutes=60)

    auto_plan, order_repo = build_auto_plan([lot], [order], machines)
    cmd = AutoPlanCommand(assign_machines=False)
    result = await auto_plan.execute(SYSTEM_ACTOR, cmd)

    assert result.proposals == []
    assert order_repo.orders[1].machine_id is None


async def test_unassigned_inspection_order_stays_machine_less_with_assign_machines_true():
    """Sibling to the assign_machines=False case above: rule 1b returns
    `[]` unconditionally for an unassigned QA order, so turning
    assign_machines on must not suddenly make Auto-Plan invent a machine
    for it either; this is the one deliberate exception to what assign_machines
    otherwise controls for every other kind of unassigned work."""
    machines = [
        make_machine(1, fabrication_method_ids=[7]),  # plain fabrication machine
        make_machine(2, is_qa_machine=True),
    ]
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

    auto_plan, order_repo = build_auto_plan([lot], [order], machines)
    cmd = AutoPlanCommand(assign_machines=True)
    result = await auto_plan.execute(SYSTEM_ACTOR, cmd)

    assert result.proposals == []
    assert order_repo.orders[1].machine_id is None


async def test_machines_level_machine_less_qa_order_is_not_reported_skipped_and_gets_dated(
    monkeypatch,
):
    """An inspection step always reports
    fabrication_method_requires_machine=False too (see the persistence
    mapper, and production_order_rules.position_is_manual's docstring;
    note this must be set explicitly here, unlike the inspection fixtures
    above, which never exercise is_manual_step=True), so a machine-less QA
    order's ctx.is_manual_step is True, exactly like a plain manual
    fabrication step's.

    _place_candidates' shared is_manual_step guard keeps the machine-level
    branch from falling through to resolve_eligible_machine_ids, which
    returns `[]` from rule 1b (an unassigned QA order is unconditionally
    ineligible for a machine) and would wrongly report the order in
    result.skipped with NO_ELIGIBLE_MACHINE, even though it is never
    actually unplaceable: it
    has no machine decision to make at all, and is dated by the manual
    bucket regardless (recompute_machine_schedule.py).

    A second, ordinary fabrication order on machine 1 is included purely
    to give this run a touched machine, so _build_result's total_touched
    gate actually runs execute_all() and the QA order's planned dates get
    populated by the manual-bucket walk too, not just its skip status."""
    pin_scheduling_clock(monkeypatch, _BEFORE_THE_FIXTURES)
    fixed_not_before = date(2026, 1, 5)  # a Monday
    machines = [
        make_machine(1, fabrication_method_ids=[1]),
        make_machine(2, is_qa_machine=True),
    ]
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

    fab_lot = make_lot(2)
    fab_order = make_order(2, lot_id=2, machine_id=1, duration_minutes=60)

    auto_plan, order_repo = build_auto_plan([qa_lot, fab_lot], [qa_order, fab_order], machines)
    cmd = AutoPlanCommand()  # planning_level='machines' default, assign_machines=False
    result = await auto_plan.execute(SYSTEM_ACTOR, cmd)

    assert result.skipped == []
    assert order_repo.orders[1].machine_id is None
    assert order_repo.orders[1].machine_pool_id is None
    assert order_repo.orders[1].planned_start == datetime(2026, 1, 5, 8, 0, tzinfo=TENANT_ZONE)
    assert order_repo.orders[1].planned_end == datetime(2026, 1, 5, 9, 0, tzinfo=TENANT_ZONE)
