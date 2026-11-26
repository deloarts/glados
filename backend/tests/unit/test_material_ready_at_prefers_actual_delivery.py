"""
An order item's expected_delivery_date/ready_for_pickup_date
are estimates set when the item was ordered, once the item has actually
arrived, the item's real delivery_date must be used instead, or the
earliest-start calculation stays pinned to a stale estimate (which can be
well after the item actually showed up), delaying a lot's only/first
production order for no reason and guaranteeing it misses its
required_delivery_date. Covers both call sites in scheduling_context.py that feed
an order item's dates into the readiness calc: resolve_material_ready_at
(position 1's input-material gate) and resolve_predecessor_ready_at's
EXTERNAL branch (a preceding EXTERNAL/MIXED position). No database, no
HTTP.
"""

from datetime import UTC
from datetime import date
from datetime import datetime

from src.modules.fulfillment.application.services.scheduling_context import SchedulingRepos
from src.modules.fulfillment.application.services.scheduling_context import (
    _prefetch_material_ready_at_by_lot,
)
from src.modules.fulfillment.application.services.scheduling_context import (
    resolve_material_ready_at,
)
from src.modules.fulfillment.application.services.scheduling_context import (
    resolve_predecessor_ready_at,
)
from src.modules.fulfillment.domain.entities.lot_position import LotPosition
from src.modules.fulfillment.domain.entities.order_item import OrderItem
from src.modules.fulfillment.domain.entities.production_lot import ProductionLot
from src.modules.fulfillment.domain.entities.source_item_allocation import (
    SourceItemDemandAllocation,
)
from src.modules.fulfillment.domain.entities.source_item_demand_item import SourceItemDemandItem
from src.modules.fulfillment.domain.services.scheduling import compute_earliest_start
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionKind
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionStatus
from src.modules.fulfillment.domain.value_objects.lot_status import LotStatus
from src.modules.fulfillment.domain.value_objects.order_status import OrderItemStatus
from src.modules.fulfillment.domain.value_objects.order_status import OrderLineType
from src.modules.fulfillment.domain.value_objects.production_status import UrgencyClass
from src.modules.fulfillment.domain.value_objects.source_item_demand_status import (
    SourceItemDemandStatus,
)
from tests.unit._tenant_settings import TenantSettings

# A day before every fixture date, so no expected delivery here counts as late.
_BEFORE_THE_FIXTURES = date(2026, 7, 1)


def make_lot(input_demand_id: int | None) -> ProductionLot:
    return ProductionLot(
        id=49,
        created=date(2026, 7, 30),
        changed=None,
        changes=[],
        lot_number="LOT-2026-0049",
        quantity=120.0,
        status=LotStatus.PLANNED,
        priority=UrgencyClass.NORMAL,
        note=None,
        required_delivery_date=date(2026, 8, 6),
        creator_id=1,
        made_item_id=1,
        project_id=1,
        input_demand_id=input_demand_id,
    )


def make_order_item(
    id: int,
    delivery_date: date | None,
    expected_delivery_date: date | None,
    ready_for_pickup_date: date | None = None,
    lot_position_id: int | None = None,
) -> OrderItem:
    return OrderItem(
        id=id,
        created=date(2026, 7, 1),
        changed=None,
        changes=[],
        status=OrderItemStatus.DELIVERED if delivery_date else OrderItemStatus.ORDERED,
        quantity=120.0,
        quantity_delivered=120.0 if delivery_date else 0.0,
        unit="pcs",
        items_per_unit=1.0,
        price=None,
        note=None,
        ordered_date=date(2026, 7, 1),
        expected_delivery_date=expected_delivery_date,
        delivery_date=delivery_date,
        storage_place=None,
        expected_pickup_date=None,
        ready_for_pickup_date=ready_for_pickup_date,
        position=1,
        creator_id=1,
        orderer_id=None,
        receiver_id=None,
        bought_item_id=None,
        order_id=1,
        supplier_id=1,
        project_id=1,
        line_type=OrderLineType.SOURCE,
        lot_position_id=lot_position_id,
        source_item_id=1,
    )


class FakeOrderItemRepo:
    def __init__(self, items: list[OrderItem]) -> None:
        self._items = {i.id: i for i in items}
        self._by_position = {i.lot_position_id: i for i in items if i.lot_position_id is not None}

    async def get_by_ids(self, ids: list[int]) -> list[OrderItem]:
        return [self._items[i] for i in ids if i in self._items]

    async def get_by_lot_position_id(self, lot_position_id: int) -> OrderItem | None:
        return self._by_position.get(lot_position_id)


class FakeSourceItemDemandRepo:
    def __init__(self, demand: SourceItemDemandItem) -> None:
        self._demand = demand

    async def get_by_id(self, id: int) -> SourceItemDemandItem | None:
        return self._demand if id == self._demand.id else None

    async def get_by_ids(self, ids: list[int]) -> list[SourceItemDemandItem]:
        return [self._demand] if self._demand.id in ids else []


class FakeSourceItemAllocationRepo:
    def __init__(self, allocations: list[SourceItemDemandAllocation]) -> None:
        self._allocations = allocations

    async def get_by_demand_item_id(self, demand_item_id: int) -> list[SourceItemDemandAllocation]:
        return [a for a in self._allocations if a.demand_item_id == demand_item_id]

    async def get_by_demand_item_ids(self, demand_item_ids: list[int]) -> list:
        return [a for d in demand_item_ids for a in await self.get_by_demand_item_id(d)]


class FakeEmptyRepo:
    async def get_by_lot_id(self, lot_id: int) -> list:
        return []

    async def get_by_lot_ids(self, lot_ids: list[int]) -> list:
        return [a for lot_id in lot_ids for a in await self.get_by_lot_id(lot_id)]

    async def get_by_id(self, id: int):
        return None

    async def get_by_ids(self, ids: list[int]) -> list:
        return []

    async def get_by_lot_position_id(self, lot_position_id: int):
        return None

    async def get_by_demand_item_id(self, demand_item_id: int) -> list:
        return []

    async def get_by_demand_item_ids(self, demand_item_ids: list[int]) -> list:
        return [a for d in demand_item_ids for a in await self.get_by_demand_item_id(d)]


def build_repos(
    order_items: list[OrderItem],
    demand: SourceItemDemandItem | None = None,
    allocations: list[SourceItemDemandAllocation] | None = None,
) -> SchedulingRepos:
    empty = FakeEmptyRepo()
    return SchedulingRepos(
        orders=empty,
        lots=empty,
        order_items=FakeOrderItemRepo(order_items),
        source_item_demands=FakeSourceItemDemandRepo(demand) if demand else empty,
        source_item_allocations=FakeSourceItemAllocationRepo(allocations or []),
        made_item_allocations=empty,
        made_item_demands=empty,
        settings=TenantSettings(),
    )


def make_demand(id: int) -> SourceItemDemandItem:
    return SourceItemDemandItem(
        id=id,
        created=date(2026, 7, 30),
        changed=date(2026, 8, 3),
        changes=[],
        status=SourceItemDemandStatus.FULFILLED,
        quantity=120.0,
        unit="pcs",
        items_per_unit=1.0,
        high_priority=False,
        notify_on_delivery=False,
        note=None,
        desired_delivery_date=None,
        creator_id=1,
        bought_item_id=None,
        source_item_id=6,
        lot_id=49,
        project_id=4,
    )


async def test_resolve_material_ready_at_counts_a_passed_expected_date_as_today():
    """Material expected on 2026-08-17 that has not arrived by 2026-09-01
    can arrive no earlier than that day, so it counts as today."""
    demand = make_demand(19)
    order_item = make_order_item(94, delivery_date=None, expected_delivery_date=date(2026, 8, 17))
    lot = make_lot(input_demand_id=19)
    repos = build_repos(
        [order_item],
        demand=demand,
        allocations=[
            SourceItemDemandAllocation(demand_item_id=19, order_item_id=94, quantity=120.0)
        ],
    )

    today = date(2026, 9, 1)
    assert await resolve_material_ready_at(lot, repos, zone=UTC, today=today) == today


async def test_resolve_material_ready_at_prefers_actual_delivery_over_stale_expected_date():
    """An order item actually delivered 2026-08-03 (quantity_delivered ==
    quantity, status == delivered) whose expected_delivery_date estimate
    (2026-08-17, set when it was ordered) was never cleared. The lot's only
    position must be ready to start today, not 2 weeks from now."""
    demand = make_demand(19)
    order_item = make_order_item(
        94, delivery_date=date(2026, 8, 3), expected_delivery_date=date(2026, 8, 17)
    )
    lot = make_lot(input_demand_id=19)
    repos = build_repos(
        [order_item],
        demand=demand,
        allocations=[
            SourceItemDemandAllocation(demand_item_id=19, order_item_id=94, quantity=120.0)
        ],
    )

    assert await resolve_material_ready_at(lot, repos, zone=UTC) == date(2026, 8, 3)


def make_external_position(id: int = 1, sequence: int = 1) -> LotPosition:
    return LotPosition(
        id=id,
        created=date(2026, 7, 1),
        changed=None,
        changes=[],
        sequence=sequence,
        kind=LotPositionKind.EXTERNAL,
        status=LotPositionStatus.ORDERED_OR_QUEUED,
        quantity=10.0,
        quantity_completed=0.0,
        note=None,
        creator_id=1,
        lot_id=1,
    )


def make_internal_position(id: int, sequence: int) -> LotPosition:
    return LotPosition(
        id=id,
        created=date(2026, 7, 1),
        changed=None,
        changes=[],
        sequence=sequence,
        kind=LotPositionKind.INTERNAL,
        status=LotPositionStatus.PENDING,
        quantity=10.0,
        quantity_completed=0.0,
        note=None,
        creator_id=1,
        lot_id=1,
    )


async def test_external_predecessor_ready_at_prefers_actual_delivery_over_stale_estimates():
    # position (this order's own position) sits one sequence after the
    # EXTERNAL predecessor: resolve_predecessor_ready_at walks every
    # earlier position of the lot, not just the immediate one, so both
    # must be present on lot.positions.
    predecessor = make_external_position(id=1, sequence=1)
    position = make_internal_position(id=2, sequence=2)
    lot = make_lot(input_demand_id=None)
    lot.positions = [predecessor, position]
    order_item = make_order_item(
        50,
        delivery_date=date(2026, 8, 3),
        expected_delivery_date=date(2026, 8, 17),
        ready_for_pickup_date=date(2026, 7, 25),
        lot_position_id=1,
    )
    repos = build_repos([order_item])

    ready_at, chain_unknown = await resolve_predecessor_ready_at(position, lot, repos, zone=UTC)

    assert ready_at == date(2026, 8, 3)
    assert chain_unknown is False


async def test_external_predecessor_ready_at_falls_back_when_not_yet_delivered():
    predecessor = make_external_position(id=1, sequence=1)
    position = make_internal_position(id=2, sequence=2)
    lot = make_lot(input_demand_id=None)
    lot.positions = [predecessor, position]
    order_item = make_order_item(
        50,
        delivery_date=None,
        expected_delivery_date=date(2026, 8, 17),
        ready_for_pickup_date=date(2026, 7, 25),
        lot_position_id=1,
    )
    repos = build_repos([order_item])

    ready_at, chain_unknown = await resolve_predecessor_ready_at(position, lot, repos, zone=UTC)

    assert ready_at == date(2026, 7, 25)
    assert chain_unknown is False


def _two_lines_one_delivered() -> tuple[ProductionLot, SchedulingRepos]:
    """The lot's raw material on two lines: one arrived (its delivery
    stamped as a moment, as the column stores it), one still expected."""
    delivered = make_order_item(
        94,
        delivery_date=datetime(2026, 8, 3, 14, 30, tzinfo=UTC),
        expected_delivery_date=date(2026, 8, 1),
    )
    expected = make_order_item(95, delivery_date=None, expected_delivery_date=date(2026, 8, 10))
    lot = make_lot(input_demand_id=19)
    repos = build_repos(
        [delivered, expected],
        demand=make_demand(19),
        allocations=[
            SourceItemDemandAllocation(demand_item_id=19, order_item_id=94, quantity=60.0),
            SourceItemDemandAllocation(demand_item_id=19, order_item_id=95, quantity=60.0),
        ],
    )
    return lot, repos


async def test_material_ready_at_mixes_a_delivered_moment_with_an_expected_day():
    lot, repos = _two_lines_one_delivered()

    assert await resolve_material_ready_at(
        lot, repos, zone=UTC, today=_BEFORE_THE_FIXTURES
    ) == date(2026, 8, 10)


async def test_prefetched_material_ready_at_mixes_a_delivered_moment_with_an_expected_day():
    lot, repos = _two_lines_one_delivered()

    assert await _prefetch_material_ready_at_by_lot([lot], repos, UTC, _BEFORE_THE_FIXTURES) == {
        lot.id: date(2026, 8, 10)
    }


async def test_material_ready_at_of_a_delivered_line_is_its_day():
    lot, repos = _two_lines_one_delivered()
    repos.order_items._items[95].delivery_date = datetime(2026, 8, 4, 6, 0, tzinfo=UTC)

    assert await resolve_material_ready_at(lot, repos, zone=UTC) == date(2026, 8, 4)
    assert compute_earliest_start(date(2026, 8, 2), None, date(2026, 8, 4)) == date(2026, 8, 4)
