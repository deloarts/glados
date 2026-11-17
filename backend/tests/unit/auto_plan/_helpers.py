"""
SYSTEM_ACTOR/DEFAULT_WEEKLY_HOURS constants, plain entity-factory functions,
and the build_auto_plan() rig builder shared by the auto_plan test modules.
"""

from datetime import date
from datetime import datetime

from src.modules.fulfillment.application.services.scheduling_context import SchedulingRepos
from src.modules.fulfillment.application.use_cases.production_schedule.auto_plan import AutoPlan
from src.modules.fulfillment.application.use_cases.production_schedule.recompute_machine_schedule import (
    RecomputeMachineSchedule,
)
from src.modules.fulfillment.domain.entities.admin_settings.production import (
    AdminProductionSettings,
)
from src.modules.fulfillment.domain.entities.lot_position import LotPosition
from src.modules.fulfillment.domain.entities.lot_step import LotStep
from src.modules.fulfillment.domain.entities.machine_pool import MachinePool
from src.modules.fulfillment.domain.entities.production_lot import ProductionLot
from src.modules.fulfillment.domain.entities.production_machine import ProductionMachine
from src.modules.fulfillment.domain.entities.production_order import ProductionOrder
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionKind
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionStatus
from src.modules.fulfillment.domain.value_objects.lot_status import LotStatus
from src.modules.fulfillment.domain.value_objects.production_status import ProductionOrderStatus
from src.modules.fulfillment.domain.value_objects.production_status import UrgencyClass
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.value_objects.date_format import DateFormat
from src.modules.platform.domain.value_objects.language import Language
from src.modules.platform.domain.value_objects.start_page import StartPage
from src.modules.platform.domain.value_objects.theme import ThemePreset
from src.modules.platform.domain.value_objects.theme import ThemePrimary
from src.modules.platform.domain.value_objects.theme import ThemeSurface
from tests.unit._tenant_settings import TenantSettings
from tests.unit.auto_plan.fakes import FakeCalendarRepo
from tests.unit.auto_plan.fakes import FakeEmptyRepo
from tests.unit.auto_plan.fakes import FakeLotRepo
from tests.unit.auto_plan.fakes import FakeMachineRepo
from tests.unit.auto_plan.fakes import FakeOrderRepo
from tests.unit.auto_plan.fakes import FakePoolRepo
from tests.unit.auto_plan.fakes import FakeSettingsRepo
from tests.unit.fakes import FakeUnitOfWork

SYSTEM_ACTOR = User(
    id=1,
    username="system",
    full_name="System",
    email="system@example.com",
    created=datetime(2026, 1, 1),
    hashed_password="",
    is_active=True,
    is_systemuser=True,
    permissions=[],
    language=Language.enGB,
    date_format=DateFormat.ISO,
    start_page=StartPage.DASHBOARD,
    theme_preset=ThemePreset.Aura,
    theme_surface=ThemeSurface.glados,
    theme_primary=ThemePrimary.glados,
    theme_dark_mode=False,
    button_flat_style=False,
    table_gridlines=False,
    table_striped_rows=False,
)

DEFAULT_WEEKLY_HOURS = {0: 480, 1: 480, 2: 480, 3: 480, 4: 480, 5: 0, 6: 0}


def make_machine(
    id: int,
    fabrication_method_ids: list[int] | None = None,
    is_qa_machine: bool = False,
) -> ProductionMachine:
    return ProductionMachine(
        id=id,
        created=date(2026, 1, 1),
        changed=None,
        changes=[],
        archived=False,
        internal_name=f"Machine {id}",
        vendor="Acme",
        model="M1",
        fabrication_method_ids=fabrication_method_ids or [1],
        max_part_dimension=None,
        note=None,
        creator_id=1,
        is_qa_machine=is_qa_machine,
    )


def make_pool(id: int, machine_ids: list[int]) -> MachinePool:
    return MachinePool(
        id=id,
        created=date(2026, 1, 1),
        changed=None,
        changes=[],
        archived=False,
        name=f"Pool {id}",
        machine_ids=machine_ids,
        note=None,
        creator_id=1,
    )


def make_lot(
    id: int,
    required_delivery_date: date | None = None,
    priority: UrgencyClass = UrgencyClass.NORMAL,
    material_arrived: bool = True,
) -> ProductionLot:
    """material_arrived (default True): whether this lot's sequence-1
    INTERNAL position's raw material is already available. The vast
    majority of this suite's fixtures are testing priority/pinning/
    machine-selection behavior, not material timing, and need an
    immediately-startable order to do it (see scheduling.
    is_unplannable_for_missing_material: a sequence-1 INTERNAL/MIXED
    position needs a demonstrably-arrived quantity or a delivery forecast
    to be plannable at all, `input_demand_id is None` alone means
    neither exists). True sets input_demand_id (FakeLotRepo.
    get_raw_material_arrived_quantity then reports an abundant supply for
    any demand id); False leaves input_demand_id unset entirely, exactly
    the literal "no demand linked" case, for a fixture deliberately
    testing that gate itself."""
    lot = ProductionLot(
        id=id,
        created=date(2026, 1, 1),
        changed=None,
        changes=[],
        lot_number=f"LOT-{id:04d}",
        quantity=10.0,
        status=LotStatus.PLANNED,
        priority=priority,
        note=None,
        creator_id=1,
        made_item_id=1,
        project_id=1,
        input_demand_id=id if material_arrived else None,
        required_delivery_date=required_delivery_date,
    )
    position = LotPosition(
        id=id,
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
        lot_id=id,
        steps=[
            LotStep(
                id=id,
                created=date(2026, 1, 1),
                note=None,
                estimated_setup_minutes=0,
                estimated_minutes_per_piece=1.0,
                sequence=1,
                creator_id=1,
                fabrication_method_id=1,
                lot_id=id,
                position_id=id,
                source_process_id=None,
            )
        ],
    )
    lot.positions = [position]
    return lot


def make_manual_lot(id: int) -> ProductionLot:
    """A one-position lot whose single step never needs a physical
    machine (position_is_manual), used by tests exercising the manual
    (no-machine, no-pool) bucket a machine-less order can fall into."""
    lot = make_lot(id)
    lot.positions[0].steps[0].fabrication_method_requires_machine = False
    return lot


def make_order(
    id: int,
    lot_id: int,
    duration_minutes: int = 60,
    machine_id: int | None = None,
    machine_pool_id: int | None = None,
    status: ProductionOrderStatus = ProductionOrderStatus.QUEUED,
    pinned: bool = False,
    queue_sequence: int = 1,
    priority: UrgencyClass = UrgencyClass.NORMAL,
    actual_start: datetime | None = None,
    planned_start: datetime | None = None,
    planned_end: datetime | None = None,
    not_before: date | None = None,
) -> ProductionOrder:
    return ProductionOrder(
        id=id,
        created=date(2026, 1, 1),
        changed=None,
        changes=[],
        production_order_number=f"PO-{id:04d}",
        status=status,
        priority=priority,
        pinned=pinned,
        queue_sequence=queue_sequence,
        quantity=10.0,
        quantity_completed=0.0,
        estimated_duration_minutes=duration_minutes,
        note=None,
        planned_start=planned_start,
        planned_end=planned_end,
        not_before=not_before,
        actual_start=actual_start,
        actual_end=None,
        creator_id=1,
        machine_id=machine_id,
        lot_position_id=lot_id,
        machine_pool_id=machine_pool_id,
        lot_id=lot_id,
    )


def build_auto_plan(
    lots: list[ProductionLot],
    orders: list[ProductionOrder],
    machines: list[ProductionMachine],
    pools: list[MachinePool] | None = None,
    response_time_days: int = 0,
) -> tuple[AutoPlan, FakeOrderRepo]:
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
    machine_repo = FakeMachineRepo(machines)
    pool_repo = FakePoolRepo(pools or [])
    calendar_repo = FakeCalendarRepo()
    settings_repo = FakeSettingsRepo(
        AdminProductionSettings(
            id=1,
            production_order_number_format="PO-{seq:04d}",
            default_weekly_hours=DEFAULT_WEEKLY_HOURS,
            default_external_lead_days=3,
            response_time_days=response_time_days,
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
