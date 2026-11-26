"""
response_time_days threading from AdminProductionSettings through
AutoPlan.execute() down to a buffered successor start, pagination beyond
the default page size for machines/pools, and AutoPlan threading its own
already-resolved settings into RecomputeMachineSchedule instead of letting
it refetch.
"""

from datetime import UTC
from datetime import date
from datetime import datetime
from datetime import timedelta

from src.modules.fulfillment.application.dto.production_schedule_dto import AutoPlanCommand
from src.modules.fulfillment.application.services.scheduling_context import SchedulingRepos
from src.modules.fulfillment.application.use_cases.production_schedule.auto_plan import AutoPlan
from src.modules.fulfillment.application.use_cases.production_schedule.recompute_machine_schedule import (
    RecomputeMachineSchedule,
)
from src.modules.fulfillment.domain.entities.admin_settings.production import (
    AdminProductionSettings,
)
from src.modules.fulfillment.domain.entities.lot_position import LotPosition
from src.modules.fulfillment.domain.entities.order_item import OrderItem
from src.modules.fulfillment.domain.entities.production_lot import ProductionLot
from src.modules.fulfillment.domain.entities.production_machine import ProductionMachine
from src.modules.fulfillment.domain.entities.production_order import ProductionOrder
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionKind
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionStatus
from src.modules.fulfillment.domain.value_objects.production_status import ProductionOrderStatus
from src.modules.fulfillment.domain.value_objects.production_status import UrgencyClass
from tests.unit._scheduling_clock import pin_scheduling_clock
from tests.unit._tenant_settings import TenantSettings
from tests.unit.auto_plan._helpers import DEFAULT_WEEKLY_HOURS
from tests.unit.auto_plan._helpers import SYSTEM_ACTOR
from tests.unit.auto_plan._helpers import build_auto_plan
from tests.unit.auto_plan._helpers import make_lot
from tests.unit.auto_plan._helpers import make_machine
from tests.unit.auto_plan._helpers import make_order
from tests.unit.auto_plan._helpers import make_pool
from tests.unit.auto_plan.fakes import ClampingFakeMachineRepo
from tests.unit.auto_plan.fakes import ClampingFakePoolRepo
from tests.unit.auto_plan.fakes import FakeCalendarRepo
from tests.unit.auto_plan.fakes import FakeEmptyRepo
from tests.unit.auto_plan.fakes import FakeLotRepo
from tests.unit.auto_plan.fakes import FakeMachineRepo
from tests.unit.auto_plan.fakes import FakeOrderRepo
from tests.unit.auto_plan.fakes import FakePoolRepo
from tests.unit.auto_plan.fakes import FakeSettingsRepo
from tests.unit.fakes import FakeUnitOfWork
from tests.unit.scheduling_service.test_external_work_forecasts import _order_item

# The walk plans no queued order before now, and the fixtures are dated in
# January 2026.
_BEFORE_THE_FIXTURES = datetime(2026, 1, 1, tzinfo=UTC)

PREDECESSOR_SUCCESSOR_END = datetime(2026, 1, 5, 14, 0)


def build_predecessor_successor_scenario() -> tuple[
    ProductionLot, ProductionOrder, ProductionOrder, ProductionMachine
]:
    """A 2-position lot (EXTERNAL -> INTERNAL): position 1's supplier line
    (predecessor_line) was delivered at PREDECESSOR_SUCCESSOR_END, position
    2's order is a fresh QUEUED candidate on a different machine; the shared
    scenario behind every response_time_days AutoPlan-level test below. The
    response time buffers an arrival, so position 1 is external. Returns
    fresh objects each call, since AutoPlan.execute() mutates them."""
    machine = make_machine(1)
    lot = make_lot(1)
    predecessor_position = LotPosition(
        id=100,
        created=date(2026, 1, 1),
        changed=None,
        changes=[],
        sequence=1,
        kind=LotPositionKind.EXTERNAL,
        status=LotPositionStatus.ORDERED_OR_QUEUED,
        quantity=10.0,
        quantity_completed=10.0,
        note=None,
        creator_id=1,
        lot_id=1,
        steps=[],
    )
    successor_position = lot.positions[0]
    successor_position.sequence = 2
    lot.positions = [predecessor_position, successor_position]

    predecessor_order = ProductionOrder(
        id=999,
        created=date(2026, 1, 1),
        changed=None,
        changes=[],
        production_order_number="PO-0999",
        status=ProductionOrderStatus.COMPLETED,
        priority=UrgencyClass.NORMAL,
        pinned=False,
        queue_sequence=1,
        quantity=10.0,
        quantity_completed=10.0,
        estimated_duration_minutes=60,
        note=None,
        planned_start=None,
        planned_end=PREDECESSOR_SUCCESSOR_END,
        not_before=None,
        actual_start=None,
        actual_end=PREDECESSOR_SUCCESSOR_END,
        creator_id=1,
        machine_id=2,
        lot_position_id=predecessor_position.id,
        lot_id=1,
    )
    successor_order = ProductionOrder(
        id=1,
        created=date(2026, 1, 1),
        changed=None,
        changes=[],
        production_order_number="PO-0001",
        status=ProductionOrderStatus.QUEUED,
        priority=UrgencyClass.NORMAL,
        pinned=False,
        queue_sequence=1,
        quantity=10.0,
        quantity_completed=0.0,
        estimated_duration_minutes=60,
        note=None,
        planned_start=None,
        planned_end=None,
        not_before=None,
        actual_start=None,
        actual_end=None,
        creator_id=1,
        machine_id=1,
        lot_position_id=successor_position.id,
        lot_id=1,
    )
    return lot, predecessor_order, successor_order, machine


def predecessor_line() -> OrderItem:
    """The supplier line of the scenario's position 1, delivered at
    PREDECESSOR_SUCCESSOR_END."""
    return _order_item(1, lot_position_id=100, delivery_date=PREDECESSOR_SUCCESSOR_END)


async def test_response_time_days_buffers_the_successors_earliest_start(monkeypatch):
    """AdminProductionSettings.response_time_days must reach all the way
    through AutoPlan.execute() (settings -> build_contexts -> build_
    order_context): a candidate gated by its predecessor's delivery
    starts response_time_days later when the setting is non-zero, same
    predecessor and same machine otherwise unchanged. This guards the
    threading itself; test_response_time_days_buffer.py already covers
    the buffering math in isolation."""
    pin_scheduling_clock(monkeypatch, _BEFORE_THE_FIXTURES)

    def build_scenario(response_time_days: int) -> tuple[AutoPlan, FakeOrderRepo]:
        lot, predecessor_order, successor_order, machine = build_predecessor_successor_scenario()
        return build_auto_plan(
            [lot],
            [predecessor_order, successor_order],
            [machine],
            response_time_days=response_time_days,
            order_items=[predecessor_line()],
        )

    auto_plan_unbuffered, repo_unbuffered = build_scenario(response_time_days=0)
    await auto_plan_unbuffered.execute(SYSTEM_ACTOR, AutoPlanCommand(assign_machines=False))
    auto_plan_buffered, repo_buffered = build_scenario(response_time_days=3)
    await auto_plan_buffered.execute(SYSTEM_ACTOR, AutoPlanCommand(assign_machines=False))

    unbuffered_start = repo_unbuffered.orders[1].planned_start
    buffered_start = repo_buffered.orders[1].planned_start
    assert unbuffered_start is not None
    assert buffered_start is not None
    assert unbuffered_start.date() == PREDECESSOR_SUCCESSOR_END.date()
    assert buffered_start.date() == PREDECESSOR_SUCCESSOR_END.date() + timedelta(days=3)


async def test_response_time_days_command_override_replaces_global_default(monkeypatch):
    """AutoPlanCommand.response_time_days, when set, overrides the global
    AdminProductionSettings.response_time_days for just this run."""
    pin_scheduling_clock(monkeypatch, _BEFORE_THE_FIXTURES)
    lot, predecessor_order, successor_order, machine = build_predecessor_successor_scenario()
    # Global default is 1 day; the per-run override below must win.
    auto_plan, order_repo = build_auto_plan(
        [lot],
        [predecessor_order, successor_order],
        [machine],
        response_time_days=1,
        order_items=[predecessor_line()],
    )

    # +2 days (Mon -> Wed) rather than a larger value that would cross the
    # weekend and need weekend-rollover math to predict here too.
    cmd = AutoPlanCommand(assign_machines=False, response_time_days=2)
    await auto_plan.execute(SYSTEM_ACTOR, cmd)

    successor_start = order_repo.orders[1].planned_start
    assert successor_start is not None
    assert successor_start.date() == PREDECESSOR_SUCCESSOR_END.date() + timedelta(days=2)


# ══════════════════════════════════════════════════════════════════════
# Silent 100-row truncation in the machine/pool candidate scan
# ══════════════════════════════════════════════════════════════════════


def _build_auto_plan_with_repos(
    lots: list[ProductionLot],
    orders: list[ProductionOrder],
    machine_repo,
    pool_repo,
    settings_repo=None,
) -> tuple[AutoPlan, FakeOrderRepo]:
    """Twin of build_auto_plan above, but takes already-constructed
    machine/pool repos instead of always wrapping plain lists in
    FakeMachineRepo/FakePoolRepo; this lets the tests below plug in the
    clamping fakes without touching build_auto_plan's signature (no other
    test needs that). settings_repo: optional, defaults to the same fixed
    FakeSettingsRepo build_auto_plan uses; the test below plugs in
    a counting variant instead."""
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
    calendar_repo = FakeCalendarRepo()
    settings_repo = settings_repo or FakeSettingsRepo(
        AdminProductionSettings(
            id=1,
            production_order_number_format="PO-{seq:04d}",
            default_weekly_hours=DEFAULT_WEEKLY_HOURS,
            default_external_lead_days=3,
            response_time_days=0,
            require_qa=False,
        )
    )
    uow = FakeUnitOfWork()
    recompute = RecomputeMachineSchedule(
        repos,
        machine_repo,
        calendar_repo,
        settings_repo,
        pool_repo,
        uow=uow,  # type: ignore[arg-type]
    )
    auto_plan = AutoPlan(
        repos,
        machine_repo,
        calendar_repo,
        settings_repo,
        recompute,
        pool_repo,
        uow=uow,  # type: ignore[arg-type]
    )
    return auto_plan, order_repo


async def test_auto_plan_considers_more_than_default_page_size_machines():
    """`auto_plan.py` reads machines with get_all(), unpaginated, because
    `self._machines.get_multi(ProductionMachineFilterDto())`, against the
    real repository, silently clamps to DEFAULT_PAGE_SIZE=100 when the
    filter carries no explicit limit (pagination.py's clamp_page). 150
    machines here, but only #150 is capable (fabrication_method_ids=[1]
    matches the lot's step; the other 149 carry a non-matching method);
    with a get_multi call and ClampingFakeMachineRepo's real clamping,
    machine #150 would fall outside the first-100 page and the order would
    never be assigned. AutoPlan must consider all 150."""
    machines = [make_machine(i, fabrication_method_ids=[999]) for i in range(1, 150)]
    machines.append(make_machine(150, fabrication_method_ids=[1]))
    lot = make_lot(1)
    order = make_order(1, lot_id=1, machine_id=None, duration_minutes=60)

    machine_repo = ClampingFakeMachineRepo(machines)
    pool_repo = ClampingFakePoolRepo([])
    auto_plan, order_repo = _build_auto_plan_with_repos([lot], [order], machine_repo, pool_repo)

    cmd = AutoPlanCommand(assign_machines=True)
    result = await auto_plan.execute(SYSTEM_ACTOR, cmd)

    assert len(result.proposals) == 1
    assert order_repo.orders[1].machine_id == 150


async def test_auto_plan_considers_more_than_default_page_size_pools():
    """Pool twin of the machine truncation test above:
    planning_level="pools", 150 pools, only pool #150 has a member
    capable of the lot's fabrication method."""
    capable_machine = make_machine(1, fabrication_method_ids=[1])
    incapable_machine = make_machine(2, fabrication_method_ids=[999])
    machines = [incapable_machine, capable_machine]
    pools = [make_pool(i, machine_ids=[2]) for i in range(1, 150)]
    pools.append(make_pool(150, machine_ids=[1]))
    lot = make_lot(1)
    order = make_order(1, lot_id=1, machine_id=None, machine_pool_id=None, duration_minutes=60)

    machine_repo = ClampingFakeMachineRepo(machines)
    pool_repo = ClampingFakePoolRepo(pools)
    auto_plan, order_repo = _build_auto_plan_with_repos([lot], [order], machine_repo, pool_repo)

    cmd = AutoPlanCommand(planning_level="pools")
    result = await auto_plan.execute(SYSTEM_ACTOR, cmd)

    assert len(result.proposals) == 1
    assert order_repo.orders[1].machine_pool_id == 150


# ══════════════════════════════════════════════════════════════════════
# Thread resolved settings into RecomputeMachineSchedule
# ══════════════════════════════════════════════════════════════════════


class CountingFakeSettingsRepo(FakeSettingsRepo):
    """Counts get_production() calls; proves AutoPlan threads its
    already-resolved AdminProductionSettings into its
    RecomputeMachineSchedule.execute_all() call rather than letting it
    re-fetch its own copy."""

    def __init__(self, settings: AdminProductionSettings) -> None:
        super().__init__(settings)
        self.get_production_calls = 0

    async def get_production(self) -> AdminProductionSettings:
        self.get_production_calls += 1
        return self.settings


async def test_auto_plan_threads_resolved_settings_into_recompute_avoiding_refetch():
    """Two machines, one QUEUED order already on each (assign_machines
    defaults to False, so each candidate stays on its own current
    machine, resolve_eligible_machine_ids' "stick to current machine"
    rule); both machines end up touched. AutoPlan hands its resolved
    settings to RecomputeMachineSchedule, so AdminProductionSettings is
    fetched exactly once, not again per touched machine (3 calls here)."""
    machine1 = make_machine(1)
    machine2 = make_machine(2)
    lot1 = make_lot(1)
    lot2 = make_lot(2)
    order1 = make_order(1, lot_id=1, machine_id=1, duration_minutes=60)
    order2 = make_order(2, lot_id=2, machine_id=2, duration_minutes=60)

    settings_repo = CountingFakeSettingsRepo(
        AdminProductionSettings(
            id=1,
            production_order_number_format="PO-{seq:04d}",
            default_weekly_hours=DEFAULT_WEEKLY_HOURS,
            default_external_lead_days=3,
            response_time_days=0,
            require_qa=False,
        )
    )
    auto_plan, _order_repo = _build_auto_plan_with_repos(
        [lot1, lot2],
        [order1, order2],
        FakeMachineRepo([machine1, machine2]),
        FakePoolRepo([]),
        settings_repo=settings_repo,
    )

    cmd = AutoPlanCommand()
    result = await auto_plan.execute(SYSTEM_ACTOR, cmd)

    assert len(result.proposals) == 2
    assert {p.after_machine_id for p in result.proposals} == {1, 2}
    assert settings_repo.get_production_calls == 1


async def test_response_time_days_omitted_falls_back_to_global_default(monkeypatch):
    """cmd.response_time_days left at its None default must use the
    global AdminProductionSettings value, not 0."""
    pin_scheduling_clock(monkeypatch, _BEFORE_THE_FIXTURES)
    lot, predecessor_order, successor_order, machine = build_predecessor_successor_scenario()
    auto_plan, order_repo = build_auto_plan(
        [lot],
        [predecessor_order, successor_order],
        [machine],
        response_time_days=4,
        order_items=[predecessor_line()],
    )

    cmd = AutoPlanCommand(assign_machines=False)
    await auto_plan.execute(SYSTEM_ACTOR, cmd)

    successor_start = order_repo.orders[1].planned_start
    assert successor_start is not None
    assert successor_start.date() == PREDECESSOR_SUCCESSOR_END.date() + timedelta(days=4)
