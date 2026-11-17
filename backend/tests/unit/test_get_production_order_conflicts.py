"""
Use-case test verifying that GetProductionOrder/GetProductionOrders
populate ProductionOrderResult.conflicts, including NO_MACHINE_ASSIGNED
for an order sitting in the unassigned bucket. No database, no HTTP.
"""

from datetime import UTC
from datetime import date
from datetime import datetime

import pytest

from src.modules.fulfillment.application.services import scheduling_context
from src.modules.fulfillment.application.services.scheduling_context import SchedulingRepos
from src.modules.fulfillment.application.use_cases.production_order.get_order import (
    GetProductionOrder,
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
from src.modules.fulfillment.domain.value_objects.schedule_conflict import ScheduleConflictReason
from tests.unit._tenant_settings import TenantSettings


def make_step() -> LotStep:
    return LotStep(
        id=1,
        created=date(2026, 1, 1),
        note=None,
        estimated_setup_minutes=10,
        estimated_minutes_per_piece=2.0,
        sequence=1,
        creator_id=1,
        fabrication_method_id=1,
        lot_id=1,
        position_id=1,
        source_process_id=None,
    )


def make_position() -> LotPosition:
    return LotPosition(
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
        steps=[make_step()],
    )


def make_lot(position: LotPosition) -> ProductionLot:
    return ProductionLot(
        id=1,
        created=date(2026, 1, 1),
        changed=None,
        changes=[],
        lot_number="LOT-0001",
        quantity=10.0,
        status=LotStatus.PARTIALLY_PLANNED,
        priority=UrgencyClass.NORMAL,
        note=None,
        creator_id=1,
        made_item_id=1,
        project_id=1,
        input_demand_id=None,
        positions=[position],
    )


def make_order(machine_id: int | None, machine_pool_id: int | None = None) -> ProductionOrder:
    return ProductionOrder(
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
        estimated_duration_minutes=30,
        note=None,
        planned_start=None,
        planned_end=None,
        not_before=None,
        actual_start=None,
        actual_end=None,
        creator_id=1,
        machine_id=machine_id,
        machine_pool_id=machine_pool_id,
        lot_position_id=1,
        lot_id=1,
    )


def make_machine(id: int, fabrication_method_ids: list[int]) -> ProductionMachine:
    return ProductionMachine(
        id=id,
        created=date(2026, 1, 1),
        changed=None,
        changes=[],
        archived=False,
        internal_name=f"Machine {id}",
        vendor="Acme",
        model="M1",
        fabrication_method_ids=fabrication_method_ids,
        max_part_dimension=None,
        note=None,
        creator_id=1,
    )


def make_pool(id: int, machines: list[ProductionMachine]) -> MachinePool:
    return MachinePool(
        id=id,
        created=date(2026, 1, 1),
        changed=None,
        changes=[],
        archived=False,
        name=f"Pool {id}",
        machine_ids=[m.id for m in machines],
        note=None,
        creator_id=1,
        machines=machines,
    )


class FakeOrderRepo:
    def __init__(self, order: ProductionOrder) -> None:
        self._order = order

    async def get_by_id(self, id: int) -> ProductionOrder | None:
        return self._order if id == self._order.id else None

    async def get_by_lot_position_id(self, lot_position_id: int) -> list[ProductionOrder]:
        return [self._order] if self._order.lot_position_id == lot_position_id else []

    async def get_by_lot_position_ids(self, lot_position_ids: list[int]) -> list[ProductionOrder]:
        return [self._order] if self._order.lot_position_id in lot_position_ids else []


class FakeLotRepo:
    def __init__(self, lot: ProductionLot) -> None:
        self._lot = lot

    async def get_by_id(self, id: int) -> ProductionLot | None:
        return self._lot if id == self._lot.id else None

    async def get_by_ids(self, ids: list[int]) -> list:
        found = [await self.get_by_id(i) for i in ids]
        return [item for item in found if item is not None]

    async def get_position_by_id(self, position_id: int) -> LotPosition | None:
        return next((p for p in self._lot.positions if p.id == position_id), None)

    async def get_positions_by_ids(self, position_ids: list[int]) -> list:
        positions = [await self.get_position_by_id(i) for i in position_ids]
        return [p for p in positions if p is not None]


class FakeEmptyRepo:
    """Stand-in for the SchedulingRepos members this scenario never
    exercises (position 1, no input_demand_id, no predecessor)."""

    async def get_by_lot_id(self, lot_id: int) -> list:
        return []

    async def get_by_lot_ids(self, lot_ids: list[int]) -> list:
        return [a for lot_id in lot_ids for a in await self.get_by_lot_id(lot_id)]

    async def get_by_id(self, id: int):
        return None

    async def get_by_ids(self, ids: list[int]) -> list:
        return []

    async def get_by_demand_item_id(self, demand_item_id: int) -> list:
        return []

    async def get_by_demand_item_ids(self, demand_item_ids: list[int]) -> list:
        return [a for d in demand_item_ids for a in await self.get_by_demand_item_id(d)]

    async def get_by_lot_position_id(self, lot_position_id: int) -> list:
        return []

    async def get_by_lot_position_ids(self, lot_position_ids: list[int]) -> list:
        return []


class FakeMachineRepo:
    async def get_by_id(self, id: int):
        return None

    async def get_by_ids(self, ids: list[int]) -> list:
        found = [await self.get_by_id(i) for i in ids]
        return [item for item in found if item is not None]


class FakePoolRepo:
    def __init__(self, pool: MachinePool | None = None) -> None:
        self._pool = pool

    async def get_by_id(self, id: int) -> MachinePool | None:
        return self._pool if self._pool is not None and self._pool.id == id else None

    async def get_by_ids(self, ids: list[int]) -> list:
        found = [await self.get_by_id(i) for i in ids]
        return [item for item in found if item is not None]


def build_use_case(
    order: ProductionOrder,
    lot: ProductionLot,
    pool: MachinePool | None = None,
    timezone: str = "UTC",
) -> GetProductionOrder:
    empty = FakeEmptyRepo()
    repos = SchedulingRepos(
        orders=FakeOrderRepo(order),
        lots=FakeLotRepo(lot),
        order_items=empty,
        source_item_demands=empty,
        source_item_allocations=empty,
        made_item_allocations=empty,
        made_item_demands=empty,
        settings=TenantSettings(timezone),
    )
    return GetProductionOrder(
        order_repo=FakeOrderRepo(order),
        repos=repos,
        machine_repo=FakeMachineRepo(),
        pool_repo=FakePoolRepo(pool),
    )


async def test_unassigned_order_gets_no_machine_assigned_conflict():
    position = make_position()
    lot = make_lot(position)
    order = make_order(machine_id=None)
    use_case = build_use_case(order, lot)

    result = await use_case.execute(order.id)

    assert ScheduleConflictReason.NO_MACHINE_ASSIGNED.value in result.conflicts


async def test_fully_queued_assigned_order_on_a_clean_position_has_no_conflicts():
    """ "Clean" here means clean of capability/queue/estimate conflicts:
    the fixture's INTERNAL sequence-1 position has no input_demand_id
    linked, which _resolve_raw_material_arrived resolves to a determinate
    0.0 rather than unconstrained, so WAITING_ON_MATERIAL still applies
    (mirrors StartProductionOrder._assert_upstream_available refusing to
    start it too)."""
    position = make_position()
    lot = make_lot(position)
    order = make_order(machine_id=1)
    use_case = build_use_case(order, lot)

    result = await use_case.execute(order.id)

    assert result.conflicts == [ScheduleConflictReason.WAITING_ON_MATERIAL.value]


@pytest.mark.parametrize(("timezone", "late"), [("Europe/Vienna", True), ("UTC", False)])
async def test_past_target_date_compares_the_planned_end_on_the_tenant_day(timezone, late):
    """23:30 UTC on the target date is 01:30 on the next day in Vienna, so
    the order is late for a Vienna tenant and on time for a UTC one."""
    position = make_position()
    lot = make_lot(position)
    lot.required_delivery_date = date(2026, 7, 27)
    order = make_order(machine_id=None)
    order.planned_start = datetime(2026, 7, 27, 22, 0, tzinfo=UTC)
    order.planned_end = datetime(2026, 7, 27, 23, 30, tzinfo=UTC)
    use_case = build_use_case(order, lot, timezone=timezone)

    result = await use_case.execute(order.id)

    assert (ScheduleConflictReason.PAST_TARGET_DATE.value in result.conflicts) is late


async def test_completed_order_always_has_no_conflicts():
    position = make_position()
    lot = make_lot(position)
    order = make_order(machine_id=1)
    order.status = ProductionOrderStatus.COMPLETED
    use_case = build_use_case(order, lot)

    result = await use_case.execute(order.id)

    assert result.conflicts == []


async def test_can_start_true_for_live_lot():
    """Control for test_can_start_false_for_terminal_lot: a QUEUED order on
    a live lot with an assigned machine is startable on state grounds. The
    lot is an alteration/rework run so sequence-1 raw-material gating is not
    what drives can_start here, the lot status is."""
    position = make_position()
    lot = make_lot(position)
    lot.source_made_item_id = 99  # alteration: exempt from raw-material gating
    order = make_order(machine_id=1)
    use_case = build_use_case(order, lot)

    result = await use_case.execute(order.id)

    assert result.can_start is True


async def test_can_start_false_for_terminal_lot():
    """Read-model half of the terminal-lot start rule: _resolve_can_start mirrors
    _assert_lot_startable, so a live order under a force-canceled or
    -completed lot must not be offered as startable."""
    for terminal in (LotStatus.CANCELED, LotStatus.COMPLETED):
        position = make_position()
        lot = make_lot(position)
        lot.source_made_item_id = 99  # would otherwise be startable
        lot.status = terminal
        order = make_order(machine_id=1)
        use_case = build_use_case(order, lot)

        result = await use_case.execute(order.id)

        assert result.can_start is False


# ── Pool-first planning: ─────────────────────────────────────────────


async def test_pool_assigned_order_does_not_get_no_machine_assigned_conflict():
    """In scheduling_context.compute_conflicts_for_orders: a pool-assigned order
    (machine_id None, machine_pool_id set) is a deliberate planner
    decision, not a bare absence of one; mirrors the
    scheduling.schedule_unassigned_orders fix at the other site."""
    position = make_position()
    lot = make_lot(position)
    order = make_order(machine_id=None, machine_pool_id=7)
    pool = make_pool(7, machines=[make_machine(1, fabrication_method_ids=[1])])
    use_case = build_use_case(order, lot, pool=pool)

    result = await use_case.execute(order.id)

    assert ScheduleConflictReason.NO_MACHINE_ASSIGNED.value not in result.conflicts


async def test_pool_assigned_order_gets_capability_mismatch_when_pool_no_longer_covers_position():
    """A pool membership edit can shrink the pool's derived
    capability intersection out from under an already-assigned order;
    this is how that surfaces: assert_pool_capability_match rejects the
    position because none of the pool's members cover fabrication method
    1, which the position's own step requires."""
    position = make_position()  # requires fabrication_method_id=1
    lot = make_lot(position)
    order = make_order(machine_id=None, machine_pool_id=7)
    pool = make_pool(7, machines=[make_machine(1, fabrication_method_ids=[2])])
    use_case = build_use_case(order, lot, pool=pool)

    result = await use_case.execute(order.id)

    assert ScheduleConflictReason.CAPABILITY_MISMATCH.value in result.conflicts
    assert ScheduleConflictReason.NO_MACHINE_ASSIGNED.value not in result.conflicts


async def test_pool_assigned_order_with_covering_pool_has_no_conflicts():
    """ "No conflicts" from the pool/capability angle this test targets,
    same WAITING_ON_MATERIAL caveat as
    test_fully_queued_assigned_order_on_a_clean_position_has_no_conflicts
    above: the fixture's sequence-1 position has no input_demand_id."""
    position = make_position()
    lot = make_lot(position)
    order = make_order(machine_id=None, machine_pool_id=7)
    pool = make_pool(7, machines=[make_machine(1, fabrication_method_ids=[1])])
    use_case = build_use_case(order, lot, pool=pool)

    result = await use_case.execute(order.id)

    assert result.conflicts == [ScheduleConflictReason.WAITING_ON_MATERIAL.value]


async def test_truly_unassigned_order_still_gets_no_machine_assigned_conflict():
    """Sanity check that the exemption only applies to pool-assigned orders: an order
    with neither a machine nor a pool is unaffected."""
    position = make_position()
    lot = make_lot(position)
    order = make_order(machine_id=None, machine_pool_id=None)
    use_case = build_use_case(order, lot)

    result = await use_case.execute(order.id)

    assert ScheduleConflictReason.NO_MACHINE_ASSIGNED.value in result.conflicts


# ── a bug in the capability check must not read as a mismatch ──────────


class FakeMachineRepoWithMachine:
    def __init__(self, machine: ProductionMachine) -> None:
        self._machine = machine

    async def get_by_id(self, id: int) -> ProductionMachine | None:
        return self._machine if id == self._machine.id else None

    async def get_by_ids(self, ids: list[int]) -> list:
        found = [await self.get_by_id(i) for i in ids]
        return [item for item in found if item is not None]


def _raise_attribute_error(*args, **kwargs):
    raise AttributeError("boom")


async def test_capability_check_bug_on_a_machine_propagates_instead_of_being_misclassified(
    monkeypatch,
):
    """assert_capability_match raises only MachineCapabilityMismatchError
    for a real mismatch. Anything else (an AttributeError here, standing
    in for a genuine bug) must propagate rather than being silently
    absorbed into a CAPABILITY_MISMATCH badge, so no conflicts are ever
    produced for this order."""
    position = make_position()
    lot = make_lot(position)
    order = make_order(machine_id=1)
    machine = make_machine(1, fabrication_method_ids=[1])
    empty = FakeEmptyRepo()
    repos = SchedulingRepos(
        orders=FakeOrderRepo(order),
        lots=FakeLotRepo(lot),
        order_items=empty,
        source_item_demands=empty,
        source_item_allocations=empty,
        made_item_allocations=empty,
        made_item_demands=empty,
        settings=TenantSettings(),
    )
    use_case = GetProductionOrder(
        order_repo=FakeOrderRepo(order),
        repos=repos,
        machine_repo=FakeMachineRepoWithMachine(machine),
        pool_repo=FakePoolRepo(),
    )
    monkeypatch.setattr(scheduling_context, "assert_capability_match", _raise_attribute_error)

    with pytest.raises(AttributeError):
        await use_case.execute(order.id)


async def test_capability_check_bug_on_a_pool_propagates_instead_of_being_misclassified(
    monkeypatch,
):
    position = make_position()  # requires fabrication_method_id=1
    lot = make_lot(position)
    order = make_order(machine_id=None, machine_pool_id=7)
    pool = make_pool(7, machines=[make_machine(1, fabrication_method_ids=[1])])
    use_case = build_use_case(order, lot, pool=pool)
    monkeypatch.setattr(scheduling_context, "assert_pool_capability_match", _raise_attribute_error)

    with pytest.raises(AttributeError):
        await use_case.execute(order.id)
