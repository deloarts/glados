"""
Characterization coverage for GetScheduleBoard, starting with the silent
page-size truncation: GetScheduleBoard puts every machine/pool its repos
return directly into the result (no capability filtering the way AutoPlan
does), so a truncation is directly observable as a wrong-length result
list; no eligibility scenario is needed the way auto_plan.py's equivalent
tests build one.

The tests also cover the board's walk: GetScheduleBoard runs one
scheduling.schedule_all() walk (via
_walk_inputs.build_schedule_walk_inputs), so a pool order floating onto a
member machine reserves real capacity on that machine's own board row,
is_floating/trial_machine_id surface that provenance on the read model,
and MachineCapacityDayResult carries overbooked_minutes. Lot/order
fixtures (make_lot, make_manual_lot,
make_order, FakeLotRepo) are imported from tests/unit/auto_plan/ rather
than duplicated, exactly as test_recompute_machine_schedule.py already
does for the same reason: the two suites must not quietly drift on what a
"queued INTERNAL sequence-1 order" fixture looks like.

In-memory fakes only, no database, no HTTP.
"""

import dataclasses
from datetime import UTC
from datetime import date
from datetime import datetime
from types import SimpleNamespace

from src.modules.fulfillment.application.services.scheduling_context import SchedulingRepos
from src.modules.fulfillment.application.use_cases.production_schedule.get_schedule_board import (
    GetScheduleBoard,
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
from src.modules.fulfillment.domain.value_objects.production_status import ProductionOrderStatus
from src.modules.fulfillment.domain.value_objects.production_status import UrgencyClass
from src.modules.fulfillment.domain.value_objects.schedule_conflict import ScheduleConflictReason
from src.modules.platform.adapters.outbound.persistence.pagination import clamp_page
from tests.unit._scheduling_clock import pin_scheduling_clock
from tests.unit._tenant_settings import TenantSettings
from tests.unit.auto_plan._helpers import make_lot
from tests.unit.auto_plan._helpers import make_manual_lot
from tests.unit.auto_plan._helpers import make_order
from tests.unit.auto_plan.fakes import FakeLotRepo

# The walk plans no queued order before now, and the fixtures are dated in
# January 2026.
_BEFORE_THE_FIXTURES = datetime(2026, 1, 1, tzinfo=UTC)

DEFAULT_WEEKLY_HOURS = {0: 480, 1: 480, 2: 480, 3: 480, 4: 480, 5: 0, 6: 0}

# 2026-01-05 is a Monday (a working day under DEFAULT_WEEKLY_HOURS above),
# used as a fixed `not_before` floor so every dated fixture below lands on
# a predictable calendar date/hour regardless of when the suite actually
# runs (see compute_earliest_start: not_before wins via max() even when,
# as here, it sits in the past relative to wall-clock "now").
MONDAY = date(2026, 1, 5)


def make_machine(id: int) -> ProductionMachine:
    return ProductionMachine(
        id=id,
        created=date(2026, 1, 1),
        changed=None,
        changes=[],
        archived=False,
        internal_name=f"Machine {id}",
        vendor="Acme",
        model="M1",
        fabrication_method_ids=[1],
        max_part_dimension=None,
        note=None,
        creator_id=1,
    )


def make_pool(id: int, machine_ids: list[int] | None = None) -> MachinePool:
    return MachinePool(
        id=id,
        created=date(2026, 1, 1),
        changed=None,
        changes=[],
        archived=False,
        name=f"Pool {id}",
        machine_ids=machine_ids or [],
        note=None,
        creator_id=1,
    )


# ══════════════════════════════════════════════════════════════════════
# Fakes
# ══════════════════════════════════════════════════════════════════════


class FakeOrderRepo:
    """Board's own order fake. Defaults to holding no orders at all,
    keeps every truncation test focused purely on the machine/pool
    roster returned, without needing lot/position fixtures build_contexts
    would otherwise chase. A test that DOES need real scheduling behavior
    passes `orders=[...]` (see _build_board)."""

    def __init__(self, orders: list[ProductionOrder] | None = None) -> None:
        self.orders = {o.id: o for o in (orders or [])}

    async def get_by_lot_position_id(self, lot_position_id: int) -> list[ProductionOrder]:
        return [o for o in self.orders.values() if o.lot_position_id == lot_position_id]

    async def get_by_lot_position_ids(self, lot_position_ids: list[int]) -> list[ProductionOrder]:
        return [o for o in self.orders.values() if o.lot_position_id in lot_position_ids]

    async def get_by_machine_id(self, machine_id: int | None) -> list[ProductionOrder]:
        return [o for o in self.orders.values() if o.machine_id == machine_id]

    async def get_all_non_terminal(self) -> list[ProductionOrder]:
        # Stub for the port method GetScheduleBoard calls. It
        # mirrors tests/unit/auto_plan/fakes.py::FakeOrderRepo.get_all_non_terminal
        # exactly (same port surface, deliberately not imported from there
        # since this fake's constructor shape, orders optional and
        # defaulting to none, differs from that module's mandatory-orders
        # one).
        terminal = {ProductionOrderStatus.COMPLETED.value, ProductionOrderStatus.CANCELED.value}
        return sorted(
            (o for o in self.orders.values() if o.status not in terminal),
            key=lambda o: (o.queue_sequence, o.id),
        )


class FakeEmptyRepo:
    async def get_by_id(self, id: int):
        return None

    async def get_by_ids(self, ids: list[int]) -> list:
        return []

    async def get_by_lot_id(self, lot_id: int) -> list:
        return []

    async def get_by_lot_ids(self, lot_ids: list[int]) -> list:
        return [a for lot_id in lot_ids for a in await self.get_by_lot_id(lot_id)]

    async def get_by_lot_position_id(self, lot_position_id: int):
        return None

    async def get_by_lot_position_ids(self, lot_position_ids: list[int]) -> list:
        return []

    async def get_by_demand_item_id(self, demand_item_id: int) -> list:
        return []

    async def get_by_demand_item_ids(self, demand_item_ids: list[int]) -> list:
        return [a for d in demand_item_ids for a in await self.get_by_demand_item_id(d)]


class FakeCalendarRepo:
    async def get_working_hours_by_machine_id(self, machine_id: int):
        return None

    async def get_working_hours_by_machine_ids(self, machine_ids: list[int]) -> list:
        return []

    async def get_exceptions_by_machine_id(self, machine_id: int) -> list:
        return []

    async def get_exceptions_by_machine_ids(self, machine_ids: list[int]) -> list:
        return []

    async def get_holidays(self) -> list:
        return []


class FakeSettingsRepo:
    def __init__(self, settings: AdminProductionSettings) -> None:
        self.settings = settings

    async def get_production(self) -> AdminProductionSettings:
        return self.settings

    async def get_general(self) -> SimpleNamespace:
        # Only the tenant timezone is read; UTC keeps calendar hours in UTC.
        return SimpleNamespace(default_timezone="UTC")


class ClampingFakeMachineRepo:
    """Mirrors the real repository's pagination behavior (clamp_page +
    slice) for get_multi, so a 150-machine fixture actually exercises the
    DEFAULT_PAGE_SIZE=100 truncation; a fake that ignores filters (as a
    plain get_multi stub would) could never fail and proves nothing.
    get_all() mirrors the real adapter's get_all: unpaginated, unaffected
    by clamp_page, which is what get_schedule_board.py calls."""

    def __init__(self, machines: list[ProductionMachine]) -> None:
        self.machines = {m.id: m for m in machines}

    async def get_by_id(self, id: int) -> ProductionMachine | None:
        return self.machines.get(id)

    async def get_by_ids(self, ids: list[int]) -> list:
        found = [await self.get_by_id(i) for i in ids]
        return [item for item in found if item is not None]

    async def get_multi(self, filters) -> tuple[int, list[ProductionMachine]]:
        values = sorted(self.machines.values(), key=lambda m: m.id)
        skip, limit = clamp_page(filters.skip, filters.limit)
        return len(values), values[skip : skip + limit]

    async def get_all(self) -> list[ProductionMachine]:
        return sorted(self.machines.values(), key=lambda m: m.id)


class ClampingFakePoolRepo:
    """Pool twin of ClampingFakeMachineRepo (see its docstring)."""

    def __init__(self, pools: list[MachinePool]) -> None:
        self.pools = {p.id: p for p in pools}

    async def get_by_id(self, id: int) -> MachinePool | None:
        return self.pools.get(id)

    async def get_by_ids(self, ids: list[int]) -> list:
        found = [await self.get_by_id(i) for i in ids]
        return [item for item in found if item is not None]

    async def get_multi(self, filters) -> tuple[int, list[MachinePool]]:
        values = sorted(self.pools.values(), key=lambda p: p.id)
        skip, limit = clamp_page(filters.skip, filters.limit)
        return len(values), values[skip : skip + limit]

    async def get_all(self) -> list[MachinePool]:
        return sorted(self.pools.values(), key=lambda p: p.id)


def _build_board(
    machine_repo,
    pool_repo=None,
    orders: list[ProductionOrder] | None = None,
    lots: list[ProductionLot] | None = None,
    response_time_days: int = 0,
) -> GetScheduleBoard:
    repos = SchedulingRepos(
        orders=FakeOrderRepo(orders),  # type: ignore[arg-type]
        lots=FakeLotRepo(lots or []),  # type: ignore[arg-type]
        order_items=FakeEmptyRepo(),  # type: ignore[arg-type]
        source_item_demands=FakeEmptyRepo(),  # type: ignore[arg-type]
        source_item_allocations=FakeEmptyRepo(),  # type: ignore[arg-type]
        made_item_allocations=FakeEmptyRepo(),  # type: ignore[arg-type]
        made_item_demands=FakeEmptyRepo(),  # type: ignore[arg-type]
        settings=TenantSettings(),  # type: ignore[arg-type]
    )
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
    return GetScheduleBoard(
        repos,
        machine_repo,
        FakeCalendarRepo(),  # type: ignore[arg-type]
        settings_repo,  # type: ignore[arg-type]
        pool_repo,
    )


# ══════════════════════════════════════════════════════════════════════
# Silent 100-row truncation
# ══════════════════════════════════════════════════════════════════════


async def test_schedule_board_returns_all_machines_beyond_default_page_size():
    """`self._machines.get_multi(ProductionMachineFilterDto())` against the
    real repository silently clamps to DEFAULT_PAGE_SIZE=100 when the
    filter carries no explicit limit, so the board reads machines through
    get_all. 150 machines here must all appear on the board, not just the
    first 100."""
    machines = [make_machine(i) for i in range(1, 151)]
    board = _build_board(ClampingFakeMachineRepo(machines))

    result = await board.execute(date(2026, 1, 5), date(2026, 1, 5))

    assert len(result.machines) == 150


async def test_schedule_board_returns_all_pools_beyond_default_page_size():
    """Pool twin of the machine truncation test above."""
    pools = [make_pool(i) for i in range(1, 151)]
    board = _build_board(ClampingFakeMachineRepo([]), ClampingFakePoolRepo(pools))

    result = await board.execute(date(2026, 1, 5), date(2026, 1, 5))

    assert len(result.pools) == 150


# ══════════════════════════════════════════════════════════════════════
# Floating pool capacity/is_floating/
# trial_machine_id, overbooked_minutes, pool-degrade, empty-machine rows,
# manual/unassigned lanes.
# ══════════════════════════════════════════════════════════════════════


async def test_floating_pool_order_counted_in_machine_and_pool_capacity(monkeypatch):
    """A floating pool
    order's reserved time counts toward its trial member's own machine
    row capacity, and toward the pool row's rollup, but the machine
    row's `orders` list stays machine-assigned only, while the pool row's
    `orders` list carries the floating order (flagged is_floating, with
    trial_machine_id naming the member) instead."""
    pin_scheduling_clock(monkeypatch, _BEFORE_THE_FIXTURES)
    machine1 = make_machine(1)
    pool = make_pool(100, machine_ids=[1])
    lot_a = make_lot(1)
    lot_b = make_lot(2)
    order_a = make_order(
        1, lot_id=1, machine_id=1, duration_minutes=60, queue_sequence=1, not_before=MONDAY
    )
    order_b = make_order(
        2, lot_id=2, machine_pool_id=100, duration_minutes=30, queue_sequence=1, not_before=MONDAY
    )

    board = _build_board(
        ClampingFakeMachineRepo([machine1]),
        ClampingFakePoolRepo([pool]),
        orders=[order_a, order_b],
        lots=[lot_a, lot_b],
    )
    result = await board.execute(MONDAY, MONDAY)

    machine_result = result.machines[0]
    assert [o.order_id for o in machine_result.orders] == [1]
    machine_order = machine_result.orders[0]
    assert machine_order.is_floating is False
    assert machine_order.trial_machine_id is None

    pool_result = result.pools[0]
    assert [o.order_id for o in pool_result.orders] == [2]
    pool_order = pool_result.orders[0]
    assert pool_order.is_floating is True
    assert pool_order.trial_machine_id == 1
    # (b) no overlap: the floating order's own placement must start no
    # earlier than the machine-assigned order's commitment ends.
    assert pool_order.planned_start is not None
    assert machine_order.planned_end is not None
    assert pool_order.planned_start >= machine_order.planned_end

    # order_a's 60 booked minutes + order_b's 30 floating minutes both
    # land on 2026-01-05: the machine row (the trial member) and the
    # pool row (its sole member) must both show the combined total, and
    # neither is overbooked (90 << 480 available on a Monday).
    assert machine_result.capacity[0].booked_minutes == 90
    assert machine_result.capacity[0].overbooked_minutes == 0
    assert pool_result.capacity[0].booked_minutes == 90
    assert pool_result.capacity[0].overbooked_minutes == 0


async def test_overbooked_minutes_reflects_real_overlap_from_pinned_orders():
    """(c): overbooked_minutes = max(0, booked - available). Two pinned
    orders on the same machine, each keeping its own manually-set window
    verbatim (advance_machine_queue's pinned branch bypasses the calendar
    walk entirely, see its own docstring), overlapping in real time, is
    the one everyday way this figure moves off zero."""
    machine1 = make_machine(1)
    lot_a = make_lot(1)
    lot_b = make_lot(2)
    pinned_start = datetime(2026, 1, 5, 8, 0, tzinfo=UTC)
    pinned_end = datetime(2026, 1, 5, 13, 0, tzinfo=UTC)  # 300 minutes
    order_a = make_order(
        1,
        lot_id=1,
        machine_id=1,
        duration_minutes=300,
        queue_sequence=1,
        pinned=True,
        planned_start=pinned_start,
        planned_end=pinned_end,
    )
    order_b = make_order(
        2,
        lot_id=2,
        machine_id=1,
        duration_minutes=300,
        queue_sequence=2,
        pinned=True,
        planned_start=pinned_start,
        planned_end=pinned_end,
    )

    board = _build_board(
        ClampingFakeMachineRepo([machine1]), orders=[order_a, order_b], lots=[lot_a, lot_b]
    )
    result = await board.execute(MONDAY, MONDAY)

    day = result.machines[0].capacity[0]
    assert day.booked_minutes == 600
    assert day.available_minutes == 480
    assert day.overbooked_minutes == 120


async def test_unresolvable_pool_falls_back_to_unassigned_lane_with_same_flags():
    """(d): a pool id that can't be resolved (deleted/emptied since
    assignment, or unknown outright) degrades its whole queue to the
    unassigned lane: still flagged floating
    (it IS pool-assigned, machine_id is None, the flag is order-shape
    derived, not bucket derived) but with no trial member, since the walk
    never actually dated it, and still not flagged NO_MACHINE_ASSIGNED
    (a pool assignment is a deliberate planner decision, not a bare
    absence of one)."""
    machine1 = make_machine(1)
    lot = make_lot(1)
    order = make_order(1, lot_id=1, machine_pool_id=999, duration_minutes=30, queue_sequence=1)

    board = _build_board(
        ClampingFakeMachineRepo([machine1]),
        ClampingFakePoolRepo([]),  # pool #999 doesn't exist
        orders=[order],
        lots=[lot],
    )
    result = await board.execute(MONDAY, MONDAY)

    assert result.pools == []
    assert [o.order_id for o in result.unassigned] == [1]
    unassigned_order = result.unassigned[0]
    assert unassigned_order.is_floating is True
    assert unassigned_order.trial_machine_id is None
    assert unassigned_order.planned_start is None
    assert ScheduleConflictReason.NO_MACHINE_ASSIGNED.value not in unassigned_order.conflicts


async def test_an_archived_pool_lists_its_floating_orders_in_the_unassigned_lane(monkeypatch):
    """An archived pool has no row on the board, yet the walk still places
    its floating orders on its members and books their minutes there, so
    the orders are listed in the unassigned lane rather than nowhere."""
    pin_scheduling_clock(monkeypatch, _BEFORE_THE_FIXTURES)
    machine1 = make_machine(1)
    pool = dataclasses.replace(make_pool(100, machine_ids=[1]), archived=True)
    lot = make_lot(1)
    order = make_order(
        1, lot_id=1, machine_pool_id=100, duration_minutes=30, queue_sequence=1, not_before=MONDAY
    )

    board = _build_board(
        ClampingFakeMachineRepo([machine1]),
        ClampingFakePoolRepo([pool]),
        orders=[order],
        lots=[lot],
    )
    result = await board.execute(MONDAY, MONDAY)

    assert result.pools == []
    assert [o.order_id for o in result.unassigned] == [1]
    assert result.unassigned[0].trial_machine_id == 1
    assert result.machines[0].capacity[0].booked_minutes == 30


async def test_machine_with_no_orders_still_gets_a_capacity_row():
    """(e): every active machine gets a capacity row, even one holding no
    orders anywhere on the board right now, which is what
    extra_machine_ids (build_schedule_walk_inputs) exists for;
    without it, machine 2 here would have no calendar entry at all and
    GetScheduleBoard would KeyError building its capacity."""
    machine1 = make_machine(1)
    machine2 = make_machine(2)
    lot = make_lot(1)
    order = make_order(
        1, lot_id=1, machine_id=1, duration_minutes=60, queue_sequence=1, not_before=MONDAY
    )

    board = _build_board(ClampingFakeMachineRepo([machine1, machine2]), orders=[order], lots=[lot])
    result = await board.execute(MONDAY, MONDAY)

    machine2_result = next(m for m in result.machines if m.machine_id == 2)
    assert machine2_result.orders == []
    assert len(machine2_result.capacity) == 1
    assert machine2_result.capacity[0].booked_minutes == 0
    assert machine2_result.capacity[0].available_minutes == 480
    assert machine2_result.capacity[0].overbooked_minutes == 0


async def test_manual_step_order_lands_in_unassigned_lane_unaffected():
    """(f): the manual (machine-less-but-manual-step) bucket is unaffected
    by pool placement: still walked against the admin default calendar and
    folded into the unassigned lane, never flagged floating (machine_pool_id
    is never set for a manual position)."""
    lot = make_manual_lot(1)
    order = make_order(1, lot_id=1, duration_minutes=45, queue_sequence=1, not_before=MONDAY)

    board = _build_board(ClampingFakeMachineRepo([]), orders=[order], lots=[lot])
    result = await board.execute(MONDAY, MONDAY)

    assert [o.order_id for o in result.unassigned] == [1]
    manual_order = result.unassigned[0]
    assert manual_order.is_floating is False
    assert manual_order.trial_machine_id is None
    assert manual_order.planned_start is not None


async def test_true_unassigned_order_lands_in_unassigned_lane_unaffected():
    """(f): a plain machine-less, non-pool, non-manual order is still
    dateless and still flagged NO_MACHINE_ASSIGNED, unaffected by
    pool placement: never flagged floating (machine_pool_id is None)."""
    lot = make_lot(1)
    order = make_order(1, lot_id=1, duration_minutes=30, queue_sequence=1)

    board = _build_board(ClampingFakeMachineRepo([]), orders=[order], lots=[lot])
    result = await board.execute(MONDAY, MONDAY)

    assert [o.order_id for o in result.unassigned] == [1]
    unassigned_order = result.unassigned[0]
    assert unassigned_order.is_floating is False
    assert unassigned_order.trial_machine_id is None
    assert unassigned_order.planned_start is None
    assert ScheduleConflictReason.NO_MACHINE_ASSIGNED.value in unassigned_order.conflicts


async def test_step_one_with_unknown_material_has_no_dates_and_its_successor_is_dateless_too():
    """Decision: a sequence-1 INTERNAL order whose raw material has
    neither arrived nor has a delivery forecast (make_lot's
    material_arrived=False) gets no dates and consumes no capacity (same
    treatment as a chain-unknown order), keeps its WAITING_ON_MATERIAL
    conflict, and its sequence-2 successor is left dateless too:
    _internal_ready_at/resolve_internal_predecessor_ready_at sees only a
    None planned_end on step 1's own order (never dated by the walk) and
    reports "no date signal yet", which resolve_predecessor_ready_at
    (scheduling_context.py) treats as chain-unknown for step 2, exactly the same
    mechanism that already protects a downstream position behind an
    undated draft order, just triggered by missing material instead."""
    machine1 = make_machine(1)
    machine2 = make_machine(2)
    lot = make_lot(1, material_arrived=False)
    lot.positions.append(
        LotPosition(
            id=2,
            created=date(2026, 1, 1),
            changed=None,
            changes=[],
            sequence=2,
            kind=LotPositionKind.INTERNAL,
            status=LotPositionStatus.ORDERED_OR_QUEUED,
            quantity=10.0,
            quantity_completed=0.0,
            note=None,
            creator_id=1,
            lot_id=1,
            steps=[
                LotStep(
                    id=2,
                    created=date(2026, 1, 1),
                    note=None,
                    estimated_setup_minutes=0,
                    estimated_minutes_per_piece=1.0,
                    sequence=1,
                    creator_id=1,
                    fabrication_method_id=1,
                    lot_id=1,
                    position_id=2,
                    source_process_id=None,
                )
            ],
        )
    )
    order1 = make_order(1, lot_id=1, machine_id=1, duration_minutes=60, queue_sequence=1)
    # Not built via make_order: its lot_id/lot_position_id convention only
    # holds for a single-position lot (position.id == lot.id); this lot
    # now has two, so lot_id and lot_position_id (2) must be set
    # independently.
    order2 = ProductionOrder(
        id=2,
        created=datetime(2026, 1, 1),
        changed=None,
        changes=[],
        production_order_number="PO-0002",
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
        machine_id=2,
        lot_position_id=2,
        machine_pool_id=None,
        lot_id=1,
    )

    board = _build_board(
        ClampingFakeMachineRepo([machine1, machine2]), orders=[order1, order2], lots=[lot]
    )
    result = await board.execute(MONDAY, MONDAY)

    machine1_result = next(m for m in result.machines if m.machine_id == 1)
    step_one_order = machine1_result.orders[0]
    assert step_one_order.planned_start is None
    assert step_one_order.planned_end is None
    assert ScheduleConflictReason.WAITING_ON_MATERIAL.value in step_one_order.conflicts
    assert machine1_result.capacity[0].booked_minutes == 0

    machine2_result = next(m for m in result.machines if m.machine_id == 2)
    step_two_order = machine2_result.orders[0]
    assert step_two_order.planned_start is None
    assert step_two_order.planned_end is None
    assert machine2_result.capacity[0].booked_minutes == 0
