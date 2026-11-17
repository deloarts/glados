"""
ProductionLot.required_delivery_date, an explicit manual "finish
by this day" set directly on the lot, must win outright over the
demand-derived target date in resolve_lot_target_date. Once it does, it must
still feed PAST_TARGET_DATE the same way the demand-derived date already
did. No database, no HTTP.
"""

from datetime import UTC
from datetime import date
from datetime import datetime

from src.modules.catalogue.domain.value_objects.made_item_status import MadeItemDemandStatus
from src.modules.fulfillment.application.services.scheduling_context import SchedulingRepos
from src.modules.fulfillment.application.services.scheduling_context import build_order_context
from src.modules.fulfillment.application.services.scheduling_context import resolve_lot_target_date
from src.modules.fulfillment.domain.entities.lot_position import LotPosition
from src.modules.fulfillment.domain.entities.lot_step import LotStep
from src.modules.fulfillment.domain.entities.made_item_allocation import MadeItemDemandAllocation
from src.modules.fulfillment.domain.entities.made_item_demand_item import MadeItemDemandItem
from src.modules.fulfillment.domain.entities.production_lot import ProductionLot
from src.modules.fulfillment.domain.entities.production_order import ProductionOrder
from src.modules.fulfillment.domain.services.scheduling import compute_order_conflicts
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionKind
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionStatus
from src.modules.fulfillment.domain.value_objects.lot_status import LotStatus
from src.modules.fulfillment.domain.value_objects.production_status import ProductionOrderStatus
from src.modules.fulfillment.domain.value_objects.production_status import UrgencyClass
from src.modules.fulfillment.domain.value_objects.schedule_conflict import ScheduleConflictReason
from tests.unit._tenant_settings import TenantSettings


def make_lot(required_delivery_date: date | None = None) -> ProductionLot:
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
        required_delivery_date=required_delivery_date,
        creator_id=1,
        made_item_id=1,
        project_id=1,
        input_demand_id=None,
    )


class FakeAllocationRepo:
    def __init__(self, allocations: list[MadeItemDemandAllocation]) -> None:
        self._allocations = allocations

    async def get_by_lot_id(self, lot_id: int) -> list[MadeItemDemandAllocation]:
        return [a for a in self._allocations if a.lot_id == lot_id]

    async def get_by_lot_ids(self, lot_ids: list[int]) -> list:
        return [a for lot_id in lot_ids for a in await self.get_by_lot_id(lot_id)]


class FakeDemandRepo:
    def __init__(self, demands: list[MadeItemDemandItem]) -> None:
        self._demands = {d.id: d for d in demands}

    async def get_by_ids(self, ids: list[int]) -> list[MadeItemDemandItem]:
        return [self._demands[i] for i in ids if i in self._demands]


class FakeEmptyRepo:
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


def make_demand(id: int, desired_delivery_date: date | None) -> MadeItemDemandItem:
    return MadeItemDemandItem(
        id=id,
        created=date(2026, 1, 1),
        changed=None,
        changes=[],
        status=MadeItemDemandStatus.ALLOCATED,
        quantity=10.0,
        unit="pcs",
        items_per_unit=1.0,
        high_priority=False,
        notify_on_delivery=False,
        note=None,
        desired_delivery_date=desired_delivery_date,
        creator_id=1,
        made_item_id=1,
        project_id=1,
    )


def build_repos(
    allocations: list[MadeItemDemandAllocation], demands: list[MadeItemDemandItem]
) -> SchedulingRepos:
    empty = FakeEmptyRepo()
    return SchedulingRepos(
        orders=empty,
        lots=empty,
        order_items=empty,
        source_item_demands=empty,
        source_item_allocations=empty,
        made_item_allocations=FakeAllocationRepo(allocations),
        made_item_demands=FakeDemandRepo(demands),
        settings=TenantSettings(),
    )


async def test_prefers_manual_required_delivery_date_when_set():
    lot = make_lot(required_delivery_date=date(2026, 3, 1))
    allocation = MadeItemDemandAllocation(demand_item_id=1, lot_id=1, quantity=10.0)
    demand = make_demand(1, desired_delivery_date=date(2026, 6, 1))
    repos = build_repos([allocation], [demand])

    assert await resolve_lot_target_date(lot, repos) == date(2026, 3, 1)


async def test_falls_back_to_demand_derived_when_manual_unset():
    lot = make_lot(required_delivery_date=None)
    allocation = MadeItemDemandAllocation(demand_item_id=1, lot_id=1, quantity=10.0)
    demand = make_demand(1, desired_delivery_date=date(2026, 6, 1))
    repos = build_repos([allocation], [demand])

    assert await resolve_lot_target_date(lot, repos) == date(2026, 6, 1)


async def test_returns_none_when_neither_manual_nor_demand_date_exists():
    lot = make_lot(required_delivery_date=None)
    repos = build_repos([], [])

    assert await resolve_lot_target_date(lot, repos) is None


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


def make_order(planned_end: datetime) -> ProductionOrder:
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
        planned_end=planned_end,
        not_before=None,
        actual_start=None,
        actual_end=None,
        creator_id=1,
        machine_id=1,
        lot_position_id=1,
    )


async def test_manual_required_delivery_date_feeds_past_target_date_conflict():
    """The manual field must flow through resolve_lot_target_date into
    build_order_context's target_date, exactly like the demand-derived
    date already did: PAST_TARGET_DATE fires off whichever one
    resolve_lot_target_date actually returns."""
    lot = make_lot(required_delivery_date=date(2026, 1, 10))
    position = make_position()
    lot.positions = [position]
    order = make_order(planned_end=datetime(2026, 1, 15, 12, 0))
    repos = build_repos([], [])

    target_date = await resolve_lot_target_date(lot, repos)
    ctx = await build_order_context(
        order, lot, machine=None, repos=repos, target_date=target_date, zone=UTC
    )
    conflicts = compute_order_conflicts(ctx, order.planned_end, now=datetime(2026, 1, 5))

    assert ScheduleConflictReason.PAST_TARGET_DATE.value in conflicts


async def test_no_past_target_date_conflict_when_order_finishes_before_manual_date():
    lot = make_lot(required_delivery_date=date(2026, 1, 20))
    position = make_position()
    lot.positions = [position]
    order = make_order(planned_end=datetime(2026, 1, 15, 12, 0))
    repos = build_repos([], [])

    target_date = await resolve_lot_target_date(lot, repos)
    ctx = await build_order_context(
        order, lot, machine=None, repos=repos, target_date=target_date, zone=UTC
    )
    conflicts = compute_order_conflicts(ctx, order.planned_end, now=datetime(2026, 1, 5))

    assert ScheduleConflictReason.PAST_TARGET_DATE.value not in conflicts
