"""
Load test for Auto-Plan performance at scale: seeds a synthetic in-memory
queue, times AutoPlan.execute() (which ends in the global
RecomputeMachineSchedule walk), and counts repository calls so a per-item
query loop shows up as a number that grows with N rather than as a guess.

Deliberately in-memory, with no database and no HTTP. AutoPlan and
RecomputeMachineSchedule only do I/O through the repositories they are
handed, so async fakes with O(1) dict lookups (standing in for an indexed
SQL query) isolate the two things this measures. Repository call counts
show the query shape independently of per-call latency, since a real
database adds a roughly constant round trip per call on top. Wall-clock
growth of AutoPlan.execute() as N grows shows whether the trial-scheduling
loop is linear or quadratic in the number of candidates converging on one
machine or pool, which matters most once most orders are pool-assigned.

Usage:
    poetry run python -m scripts.load_test_auto_plan
"""

import os

# The settings module builds its config singleton at import time and
# requires these values. Throwaway defaults, mirroring tests/conftest.py, so
# the script runs without an env file; nothing here ever opens a database or
# Redis connection. Anything already set in the environment wins.
os.environ.setdefault("DEBUG", "false")
os.environ.setdefault("SECURITY__SECRET_KEY_PERSISTENT", "load-test-persistent-key")
os.environ.setdefault("SECURITY__SECRET_KEY_NON_PERSISTENT", "load-test-non-persistent-key")
os.environ.setdefault("DATABASE__URL", "sqlite:///:memory:")
os.environ.setdefault("REDIS__URL", "redis://localhost:6379/15")
os.environ.setdefault("INIT__FULL_NAME", "Load Test")
os.environ.setdefault("INIT__MAIL", "load-test@example.com")
os.environ.setdefault("INIT__PASSWORD", "load-test-password")

import asyncio
import cProfile
import io
import logging
import pstats
import random
import time
from datetime import UTC
from datetime import date
from datetime import datetime
from datetime import timedelta
from typing import Any

from src.modules.fulfillment.application.dto.production_schedule_dto import AutoPlanCommand
from src.modules.fulfillment.application.dto.production_schedule_dto import AutoPlanResult
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
from src.modules.fulfillment.domain.services.scheduling import ExternalForecast
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionKind
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionStatus
from src.modules.fulfillment.domain.value_objects.lot_status import LotStatus
from src.modules.fulfillment.domain.value_objects.production_status import ProductionOrderStatus
from src.modules.fulfillment.domain.value_objects.production_status import UrgencyClass
from src.modules.fulfillment.ports.outbound.repositories.production_order_repository import (
    ProductionOrderPlanningFields,
)
from src.modules.platform.domain.entities.admin_settings.general import AdminGeneralSettings
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.value_objects.date_format import DateFormat
from src.modules.platform.domain.value_objects.language import Language
from src.modules.platform.domain.value_objects.start_page import StartPage
from src.modules.platform.domain.value_objects.theme import ThemePreset
from src.modules.platform.domain.value_objects.theme import ThemePrimary
from src.modules.platform.domain.value_objects.theme import ThemeSurface
from src.modules.platform.infrastructure.logging.logger import log

# ══════════════════════════════════════════════════════════════════════
# Instrumented async fakes. Lookups are O(1) like an indexed query, and
# every call is counted.
# ══════════════════════════════════════════════════════════════════════

call_counts: dict[str, int] = {}

_TERMINAL = {ProductionOrderStatus.COMPLETED, ProductionOrderStatus.CANCELED}


def _count(name: str) -> None:
    call_counts[name] = call_counts.get(name, 0) + 1


class FakeOrderRepo:
    def __init__(self, orders: dict[int, ProductionOrder]) -> None:
        self.orders = orders
        self.by_position: dict[int, list[ProductionOrder]] = {}
        self.by_machine: dict[int | None, dict[int, ProductionOrder]] = {}
        for o in orders.values():
            self.by_position.setdefault(o.lot_position_id, []).append(o)
            self.by_machine.setdefault(o.machine_id, {})[o.id] = o
        self._indexed_machine = {o.id: o.machine_id for o in orders.values()}

    def _reindex(self, order: ProductionOrder) -> None:
        old_machine = self._indexed_machine.get(order.id)
        if old_machine != order.machine_id:
            self.by_machine.get(old_machine, {}).pop(order.id, None)
            self.by_machine.setdefault(order.machine_id, {})[order.id] = order
            self._indexed_machine[order.id] = order.machine_id
        self.orders[order.id] = order

    async def get_by_id(self, id: int) -> ProductionOrder | None:
        _count("orders.get_by_id")
        return self.orders.get(id)

    async def get_by_ids(self, ids: list[int]) -> list[ProductionOrder]:
        _count("orders.get_by_ids")
        return [self.orders[i] for i in ids if i in self.orders]

    async def get_by_lot_position_id(self, lot_position_id: int) -> list[ProductionOrder]:
        _count("orders.get_by_lot_position_id")
        return list(self.by_position.get(lot_position_id, []))

    async def get_by_lot_position_ids(self, lot_position_ids: list[int]) -> list[ProductionOrder]:
        _count("orders.get_by_lot_position_ids")
        return [o for pid in lot_position_ids for o in self.by_position.get(pid, [])]

    async def get_by_machine_id(self, machine_id: int | None) -> list[ProductionOrder]:
        _count("orders.get_by_machine_id")
        return sorted(
            self.by_machine.get(machine_id, {}).values(), key=lambda o: (o.queue_sequence, o.id)
        )

    async def get_by_machine_ids(self, machine_ids: list[int | None]) -> list[ProductionOrder]:
        _count("orders.get_by_machine_ids")
        return sorted(
            (o for m in set(machine_ids) for o in self.by_machine.get(m, {}).values()),
            key=lambda o: (o.queue_sequence, o.id),
        )

    async def get_all_non_terminal(self) -> list[ProductionOrder]:
        _count("orders.get_all_non_terminal")
        return sorted(
            (o for o in self.orders.values() if o.status not in _TERMINAL),
            key=lambda o: (o.queue_sequence, o.id),
        )

    async def save(self, order: ProductionOrder) -> ProductionOrder:
        _count("orders.save")
        self._reindex(order)
        return order

    async def save_schedule(self, orders: list[ProductionOrder]) -> None:
        _count("orders.save_schedule")
        for order in orders:
            self._reindex(order)

    async def save_planning_fields(self, plans: list[ProductionOrderPlanningFields]) -> None:
        _count("orders.save_planning_fields")
        for plan in plans:
            order = self.orders.get(plan.order_id)
            if order is None or order.pinned != plan.pinned_when_read:
                continue
            order.planned_start = plan.planned_start
            order.planned_end = plan.planned_end
            order.planned_by_id = plan.planned_by_id

    async def lock_queue_scope(
        self, machine_id: int | None, machine_pool_id: int | None = None
    ) -> None:
        _count("orders.lock_queue_scope")

    async def shift_queue_sequence(self, order_ids: list[int]) -> None:
        _count("orders.shift_queue_sequence")
        for order_id in order_ids:
            if order_id in self.orders:
                self.orders[order_id].queue_sequence = -order_id


class FakeLotRepo:
    def __init__(self, lots: dict[int, ProductionLot]) -> None:
        self.lots = lots
        self.positions = {p.id: p for lot in lots.values() for p in lot.positions}

    async def get_by_id(self, id: int) -> ProductionLot | None:
        _count("lots.get_by_id")
        return self.lots.get(id)

    async def get_by_ids(self, ids: list[int]) -> list[ProductionLot]:
        _count("lots.get_by_ids")
        return [self.lots[i] for i in ids if i in self.lots]

    async def get_raw_material_arrived_quantity(self, demand_id: int) -> float:
        _count("lots.get_raw_material_arrived_quantity")
        return 1_000_000.0

    async def get_raw_material_arrived_quantities(self, demand_ids: list[int]) -> dict[int, float]:
        # Every synthetic lot's raw material has already arrived, so the
        # material gate never parks a candidate.
        _count("lots.get_raw_material_arrived_quantities")
        return {d: 1_000_000.0 for d in demand_ids}

    async def get_positions_by_ids(self, position_ids: list[int]) -> list[LotPosition]:
        _count("lots.get_positions_by_ids")
        return [self.positions[i] for i in position_ids if i in self.positions]

    async def save_position(self, position: LotPosition) -> LotPosition:
        _count("lots.save_position")
        return position

    async def save_position_forecasts(self, forecasts: list[ExternalForecast]) -> None:
        _count("lots.save_position_forecasts")
        for forecast in forecasts:
            position = self.positions.get(forecast.position_id)
            if position is not None:
                position.planned_pickup_date = forecast.planned_pickup_date
                position.planned_delivery_date = forecast.planned_delivery_date


class FakeEmptyRepo:
    """Stands in for order_items, source_item_demands,
    source_item_allocations, made_item_allocations and made_item_demands.
    Every synthetic lot carries a manual delivery date and only INTERNAL
    positions, so these lookups always come back empty; they are still
    counted under `name` so a per-lot call would show up."""

    def __init__(self, name: str) -> None:
        self._name = name

    async def get_by_id(self, id: int) -> Any:
        _count(f"{self._name}.get_by_id")
        return None

    async def get_by_ids(self, ids: list[int]) -> list[Any]:
        _count(f"{self._name}.get_by_ids")
        return []

    async def get_by_lot_id(self, lot_id: int) -> list[Any]:
        _count(f"{self._name}.get_by_lot_id")
        return []

    async def get_by_lot_ids(self, lot_ids: list[int]) -> list[Any]:
        _count(f"{self._name}.get_by_lot_ids")
        return []

    async def get_by_lot_position_id(self, lot_position_id: int) -> Any:
        _count(f"{self._name}.get_by_lot_position_id")
        return None

    async def get_by_lot_position_ids(self, lot_position_ids: list[int]) -> list[Any]:
        _count(f"{self._name}.get_by_lot_position_ids")
        return []

    async def get_by_demand_item_id(self, demand_item_id: int) -> list[Any]:
        _count(f"{self._name}.get_by_demand_item_id")
        return []

    async def get_by_demand_item_ids(self, demand_item_ids: list[int]) -> list[Any]:
        _count(f"{self._name}.get_by_demand_item_ids")
        return []


class FakeMachineRepo:
    def __init__(self, machines: dict[int, ProductionMachine]) -> None:
        self.machines = machines

    async def get_by_id(self, id: int) -> ProductionMachine | None:
        _count("machines.get_by_id")
        return self.machines.get(id)

    async def get_by_ids(self, ids: list[int]) -> list[ProductionMachine]:
        _count("machines.get_by_ids")
        return [self.machines[i] for i in ids if i in self.machines]

    async def get_all(self) -> list[ProductionMachine]:
        _count("machines.get_all")
        return list(self.machines.values())


class FakePoolRepo:
    def __init__(self, pools: dict[int, MachinePool]) -> None:
        self.pools = pools

    async def get_by_id(self, id: int) -> MachinePool | None:
        _count("pools.get_by_id")
        return self.pools.get(id)

    async def get_by_ids(self, ids: list[int]) -> list[MachinePool]:
        _count("pools.get_by_ids")
        return [self.pools[i] for i in ids if i in self.pools]

    async def get_all(self) -> list[MachinePool]:
        _count("pools.get_all")
        return list(self.pools.values())


class FakeCalendarRepo:
    """Every machine uses the admin default calendar."""

    async def get_working_hours_by_machine_id(self, machine_id: int) -> None:
        _count("calendars.get_working_hours_by_machine_id")

    async def get_working_hours_by_machine_ids(self, machine_ids: list[int]) -> list[Any]:
        _count("calendars.get_working_hours_by_machine_ids")
        return []

    async def get_exceptions_by_machine_id(self, machine_id: int) -> list[Any]:
        _count("calendars.get_exceptions_by_machine_id")
        return []

    async def get_exceptions_by_machine_ids(self, machine_ids: list[int]) -> list[Any]:
        _count("calendars.get_exceptions_by_machine_ids")
        return []


class FakeSettingsRepo:
    def __init__(self, settings: AdminProductionSettings) -> None:
        self.settings = settings

    async def get_production(self) -> AdminProductionSettings:
        _count("settings.get_production")
        return self.settings

    async def get_general(self) -> AdminGeneralSettings:
        """Only default_timezone is read, to resolve the planner's calendar day."""
        _count("settings.get_general")
        return _GENERAL_SETTINGS


_GENERAL_SETTINGS = AdminGeneralSettings(
    id=1,
    company_name=None,
    company_legal_name=None,
    company_logo_key=None,
    contact_email=None,
    imprint_url=None,
    privacy_url=None,
    support_url=None,
    product_number_pattern="",
    project_number_pattern="",
    allow_headless_projects=True,
    empty_value_placeholder="-",
    office_launcher_enabled=False,
    office_sharepoint_url="",
    currency="EUR",
    default_language=Language.enGB,
    default_timezone="Europe/Vienna",
    default_date_format=DateFormat.ISO,
)


class FakeUnitOfWork:
    async def commit(self) -> None:
        _count("uow.commit")

    async def rollback(self) -> None:
        _count("uow.rollback")


# ══════════════════════════════════════════════════════════════════════
# Synthetic data generation
# ══════════════════════════════════════════════════════════════════════

SYSTEM_ACTOR = User(
    id=1,
    username="system",
    full_name="System",
    email="system@example.com",
    created=datetime(2026, 1, 1, tzinfo=UTC),
    hashed_password="",
    is_active=True,
    is_systemuser=True,  # bypasses permission checks entirely
    permissions=[],
    language=Language.enGB,
    date_format=DateFormat.ISO,
    start_page=StartPage.DASHBOARD,
    theme_preset=ThemePreset.Aura,
    theme_surface=ThemeSurface.default(),
    theme_primary=ThemePrimary.default(),
    theme_dark_mode=False,
    button_flat_style=False,
    table_gridlines=False,
    table_striped_rows=False,
)

_PRIORITIES = [
    UrgencyClass.LOW,
    UrgencyClass.NORMAL,
    UrgencyClass.HIGH,
    UrgencyClass.CRITICAL,
]


def _make_lot(i: int, rng: random.Random) -> ProductionLot:
    lot = ProductionLot(
        id=i,
        created=datetime(2026, 1, 1, tzinfo=UTC),
        changed=None,
        changes=[],
        lot_number=f"LOT-{i:05d}",
        quantity=10.0,
        status=LotStatus.PLANNED,
        priority=rng.choice(_PRIORITIES),
        note=None,
        creator_id=1,
        made_item_id=1,
        project_id=1,
        # A linked raw-material demand that FakeLotRepo reports as arrived.
        # Without one, every sequence-1 order would be skipped as waiting
        # on material and the placement loop would never run.
        input_demand_id=i,
        required_delivery_date=date(2026, 8, 3) + timedelta(days=rng.randint(1, 30)),
    )
    lot.positions = [
        LotPosition(
            id=i,
            created=datetime(2026, 1, 1, tzinfo=UTC),
            changed=None,
            changes=[],
            sequence=1,
            kind=LotPositionKind.INTERNAL,
            status=LotPositionStatus.ORDERED_OR_QUEUED,
            quantity=10.0,
            quantity_completed=0.0,
            note=None,
            creator_id=1,
            lot_id=i,
            steps=[
                LotStep(
                    id=i,
                    created=datetime(2026, 1, 1, tzinfo=UTC),
                    note=None,
                    estimated_setup_minutes=10,
                    estimated_minutes_per_piece=2.0,
                    sequence=1,
                    creator_id=1,
                    # One shared method, so every machine covers every step.
                    fabrication_method_id=1,
                    lot_id=i,
                    position_id=i,
                    source_process_id=None,
                )
            ],
        )
    ]
    return lot


def build_auto_plan(
    n_orders: int, n_machines: int, n_pools: int, pool_heavy_fraction: float, seed: int = 42
) -> AutoPlan:
    """pool_heavy_fraction is the share of orders assigned to a pool
    (machine_pool_id set, machine_id None) rather than directly to a
    machine. Many candidates converging on few eligible-machine sets is
    the shape that stresses the trial-scheduling loop hardest."""
    rng = random.Random(seed)

    machines = {
        m: ProductionMachine(
            id=m,
            created=datetime(2026, 1, 1, tzinfo=UTC),
            changed=None,
            changes=[],
            archived=False,
            internal_name=f"Machine {m}",
            vendor="Acme",
            model="M1",
            fabrication_method_ids=[1],
            max_part_dimension=None,
            note=None,
            creator_id=1,
        )
        for m in range(1, n_machines + 1)
    }
    machine_ids = list(machines)
    pools = {
        p: MachinePool(
            id=p,
            created=datetime(2026, 1, 1, tzinfo=UTC),
            changed=None,
            changes=[],
            archived=False,
            name=f"Pool {p}",
            # Round-robin split of the machines across the pools.
            machine_ids=machine_ids[(p - 1) :: n_pools],
            note=None,
            creator_id=1,
        )
        for p in range(1, n_pools + 1)
    }

    lots: dict[int, ProductionLot] = {}
    orders: dict[int, ProductionOrder] = {}
    for i in range(1, n_orders + 1):
        lot = _make_lot(i, rng)
        lots[i] = lot
        pool_assigned = rng.random() < pool_heavy_fraction
        orders[i] = ProductionOrder(
            id=i,
            created=datetime(2026, 1, 1, tzinfo=UTC),
            changed=None,
            changes=[],
            production_order_number=f"PO-{i:05d}",
            status=ProductionOrderStatus.QUEUED,
            priority=lot.priority,
            pinned=False,
            queue_sequence=i,
            quantity=10.0,
            quantity_completed=0.0,
            estimated_duration_minutes=rng.randint(30, 240),
            note=None,
            planned_start=None,
            planned_end=None,
            not_before=None,
            actual_start=None,
            actual_end=None,
            creator_id=1,
            machine_id=None if pool_assigned else rng.choice(machine_ids),
            lot_position_id=i,
            machine_pool_id=rng.choice(list(pools)) if pool_assigned else None,
            lot_id=i,
        )

    # The fakes implement only the subset of each port these code paths
    # call, hence the ignores rather than dozens of never-exercised stubs.
    settings_repo = FakeSettingsRepo(
        AdminProductionSettings(
            id=1,
            production_order_number_format="PO-{seq:04d}",
            default_weekly_hours={0: 480, 1: 480, 2: 480, 3: 480, 4: 480, 5: 0, 6: 0},
            default_external_lead_days=3,
            response_time_days=0,
            require_qa=False,
        )
    )
    repos = SchedulingRepos(
        orders=FakeOrderRepo(orders),  # type: ignore[arg-type]
        lots=FakeLotRepo(lots),  # type: ignore[arg-type]
        order_items=FakeEmptyRepo("order_items"),  # type: ignore[arg-type]
        source_item_demands=FakeEmptyRepo("source_item_demands"),  # type: ignore[arg-type]
        source_item_allocations=FakeEmptyRepo("source_item_allocations"),  # type: ignore[arg-type]
        made_item_allocations=FakeEmptyRepo("made_item_allocations"),  # type: ignore[arg-type]
        made_item_demands=FakeEmptyRepo("made_item_demands"),  # type: ignore[arg-type]
        settings=settings_repo,  # type: ignore[arg-type]
    )
    machine_repo = FakeMachineRepo(machines)
    pool_repo = FakePoolRepo(pools)
    calendar_repo = FakeCalendarRepo()
    uow = FakeUnitOfWork()
    recompute = RecomputeMachineSchedule(
        repos,
        machine_repo,  # type: ignore[arg-type]
        calendar_repo,  # type: ignore[arg-type]
        settings_repo,  # type: ignore[arg-type]
        pool_repo,  # type: ignore[arg-type]
        uow=uow,
    )
    return AutoPlan(
        repos,
        machine_repo,  # type: ignore[arg-type]
        calendar_repo,  # type: ignore[arg-type]
        settings_repo,  # type: ignore[arg-type]
        recompute,
        pool_repo,  # type: ignore[arg-type]
        uow=uow,
    )


_CMD = AutoPlanCommand(assign_machines=True, planning_level="machines")


async def _execute(auto_plan: AutoPlan) -> AutoPlanResult:
    return await auto_plan.execute(SYSTEM_ACTOR, _CMD)


def run_once(n_orders: int, n_machines: int, n_pools: int, pool_heavy_fraction: float) -> float:
    auto_plan = build_auto_plan(n_orders, n_machines, n_pools, pool_heavy_fraction)
    call_counts.clear()

    start = time.perf_counter()
    result = asyncio.run(_execute(auto_plan))
    elapsed = time.perf_counter() - start

    print(
        f"  n={n_orders:>5} machines={n_machines:>2} pools={n_pools:>2} "
        f"pool_heavy={pool_heavy_fraction:>4.1f} -> {elapsed:>7.3f}s  "
        f"({len(result.proposals)} moved, {len(result.skipped)} unplaced)\n"
        f"      calls={dict(sorted(call_counts.items()))}"
    )
    return elapsed


def profile_once(n_orders: int, n_machines: int, n_pools: int, pool_heavy_fraction: float) -> None:
    auto_plan = build_auto_plan(n_orders, n_machines, n_pools, pool_heavy_fraction)
    call_counts.clear()

    async def _profiled() -> None:
        profiler = cProfile.Profile()
        profiler.enable()
        try:
            await _execute(auto_plan)
        finally:
            profiler.disable()
        stream = io.StringIO()
        pstats.Stats(profiler, stream=stream).sort_stats("cumulative").print_stats(20)
        print(stream.getvalue())

    asyncio.run(_profiled())


_SIZES = (100, 250, 500, 1000, 2000)


def main() -> None:
    # The per-run INFO lines from AutoPlan and the recompute would bury the
    # table below.
    log.setLevel(logging.WARNING)
    print("=== Scaling: spread across many machines, direct assignment ===")
    for n in _SIZES:
        run_once(n_orders=n, n_machines=20, n_pools=2, pool_heavy_fraction=0.0)

    print()
    print("=== Scaling: pool-heavy, few pools ===")
    for n in _SIZES:
        run_once(n_orders=n, n_machines=6, n_pools=2, pool_heavy_fraction=0.9)

    print()
    print("=== cProfile breakdown at n=1000, pool-heavy ===")
    # The walk itself runs in a worker thread (anyio.to_thread), which this
    # profiler does not see; its cost shows up as time awaited in run_sync.
    profile_once(n_orders=1000, n_machines=6, n_pools=2, pool_heavy_fraction=0.9)


if __name__ == "__main__":
    main()
