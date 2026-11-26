"""
AdminProductionSettings.response_time_days: a global buffer (calendar
days) added on top of a predecessor position's ready date and a lot's
input-material ready date before either can gate the next step's
earliest start (see build_order_context in scheduling_context.py, and
compute_earliest_start in scheduling/earliest_start.py, which consumes these
two OrderSchedulingContext fields verbatim, already buffered). Never
applied to a manual not_before override. No database, no HTTP.
"""

from datetime import UTC
from datetime import date
from datetime import datetime

from src.modules.fulfillment.application.services.scheduling_context import SchedulingRepos
from src.modules.fulfillment.application.services.scheduling_context import build_order_context
from src.modules.fulfillment.domain.entities.lot_position import LotPosition
from src.modules.fulfillment.domain.entities.lot_step import LotStep
from src.modules.fulfillment.domain.entities.order_item import OrderItem
from src.modules.fulfillment.domain.entities.production_lot import ProductionLot
from src.modules.fulfillment.domain.entities.production_order import ProductionOrder
from src.modules.fulfillment.domain.entities.source_item_allocation import (
    SourceItemDemandAllocation,
)
from src.modules.fulfillment.domain.entities.source_item_demand_item import SourceItemDemandItem
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionKind
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionStatus
from src.modules.fulfillment.domain.value_objects.lot_status import LotStatus
from src.modules.fulfillment.domain.value_objects.order_status import OrderItemStatus
from src.modules.fulfillment.domain.value_objects.order_status import OrderLineType
from src.modules.fulfillment.domain.value_objects.production_status import ProductionOrderStatus
from src.modules.fulfillment.domain.value_objects.production_status import UrgencyClass
from src.modules.fulfillment.domain.value_objects.source_item_demand_status import (
    SourceItemDemandStatus,
)
from tests.unit._tenant_settings import TenantSettings


def make_step(position_id: int) -> LotStep:
    return LotStep(
        id=position_id,
        created=date(2026, 1, 1),
        note=None,
        estimated_setup_minutes=10,
        estimated_minutes_per_piece=2.0,
        sequence=position_id,
        creator_id=1,
        fabrication_method_id=1,
        lot_id=1,
        position_id=position_id,
        source_process_id=None,
    )


def make_position(id: int, sequence: int) -> LotPosition:
    return LotPosition(
        id=id,
        created=date(2026, 1, 1),
        changed=None,
        changes=[],
        sequence=sequence,
        kind=LotPositionKind.INTERNAL,
        status=LotPositionStatus.ORDERED_OR_QUEUED,
        quantity=10.0,
        quantity_completed=0.0,
        note=None,
        creator_id=1,
        lot_id=1,
        steps=[make_step(id)],
    )


def make_lot(input_demand_id: int | None = None) -> ProductionLot:
    return ProductionLot(
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
        input_demand_id=input_demand_id,
    )


def make_order(id: int, lot_position_id: int, not_before: date | None = None) -> ProductionOrder:
    return ProductionOrder(
        id=id,
        created=date(2026, 1, 1),
        changed=None,
        changes=[],
        production_order_number=f"PO-{id:04d}",
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
        not_before=not_before,
        actual_start=None,
        actual_end=None,
        creator_id=1,
        machine_id=1,
        lot_position_id=lot_position_id,
    )


def make_order_item(id: int, delivery_date: date) -> OrderItem:
    return OrderItem(
        id=id,
        created=date(2026, 1, 1),
        changed=None,
        changes=[],
        status=OrderItemStatus.DELIVERED,
        quantity=10.0,
        quantity_delivered=10.0,
        unit="pcs",
        items_per_unit=1.0,
        price=None,
        note=None,
        ordered_date=date(2026, 1, 1),
        expected_delivery_date=delivery_date,
        delivery_date=delivery_date,
        storage_place=None,
        expected_pickup_date=None,
        ready_for_pickup_date=None,
        position=1,
        creator_id=1,
        orderer_id=None,
        receiver_id=None,
        bought_item_id=None,
        order_id=1,
        supplier_id=1,
        project_id=1,
        line_type=OrderLineType.SOURCE,
        lot_position_id=None,
        source_item_id=1,
    )


class FakeOrderRepo:
    def __init__(self, orders: list[ProductionOrder]) -> None:
        self._orders = orders

    async def get_by_lot_position_id(self, lot_position_id: int) -> list[ProductionOrder]:
        return [o for o in self._orders if o.lot_position_id == lot_position_id]


class FakeOrderItemRepo:
    def __init__(self, items: list[OrderItem]) -> None:
        self._by_id = {i.id: i for i in items}

    async def get_by_ids(self, ids: list[int]) -> list[OrderItem]:
        return [self._by_id[i] for i in ids if i in self._by_id]

    async def get_by_lot_position_id(self, lot_position_id: int) -> OrderItem | None:
        return next((i for i in self._by_id.values() if i.lot_position_id == lot_position_id), None)


class FakeSourceItemDemandRepo:
    def __init__(self, demand: SourceItemDemandItem) -> None:
        self._demand = demand

    async def get_by_id(self, id: int) -> SourceItemDemandItem | None:
        return self._demand if id == self._demand.id else None


class FakeSourceItemAllocationRepo:
    def __init__(self, allocations: list[SourceItemDemandAllocation]) -> None:
        self._allocations = allocations

    async def get_by_demand_item_id(self, demand_item_id: int) -> list[SourceItemDemandAllocation]:
        return [a for a in self._allocations if a.demand_item_id == demand_item_id]

    async def get_by_demand_item_ids(self, demand_item_ids: list[int]) -> list:
        return [a for d in demand_item_ids for a in await self.get_by_demand_item_id(d)]


class FakeEmptyRepo:
    async def get_by_id(self, id: int):
        return None

    async def get_raw_material_arrived_quantity(self, demand_id: int) -> float:
        return 0.0

    async def get_raw_material_arrived_quantities(self, demand_ids: list[int]) -> dict[int, float]:
        return {d: await self.get_raw_material_arrived_quantity(d) for d in demand_ids}

    async def get_by_ids(self, ids: list[int]) -> list:
        return []

    async def get_by_lot_id(self, lot_id: int) -> list:
        return []

    async def get_by_lot_ids(self, lot_ids: list[int]) -> list:
        return [a for lot_id in lot_ids for a in await self.get_by_lot_id(lot_id)]

    async def get_by_lot_position_id(self, lot_position_id: int):
        return None

    async def get_by_demand_item_id(self, demand_item_id: int) -> list:
        return []

    async def get_by_demand_item_ids(self, demand_item_ids: list[int]) -> list:
        return [a for d in demand_item_ids for a in await self.get_by_demand_item_id(d)]


def build_repos(
    orders: list[ProductionOrder] | None = None,
    order_items: list[OrderItem] | None = None,
    demand: SourceItemDemandItem | None = None,
    allocations: list[SourceItemDemandAllocation] | None = None,
) -> SchedulingRepos:
    empty = FakeEmptyRepo()
    return SchedulingRepos(
        orders=FakeOrderRepo(orders) if orders is not None else empty,  # type: ignore[arg-type]
        lots=empty,  # type: ignore[arg-type]
        order_items=FakeOrderItemRepo(order_items) if order_items is not None else empty,  # type: ignore[arg-type]
        source_item_demands=FakeSourceItemDemandRepo(demand) if demand else empty,  # type: ignore[arg-type]
        source_item_allocations=FakeSourceItemAllocationRepo(allocations or []),  # type: ignore[arg-type]
        made_item_allocations=empty,  # type: ignore[arg-type]
        made_item_demands=empty,  # type: ignore[arg-type]
        settings=TenantSettings(),  # type: ignore[arg-type]
    )


async def test_an_in_house_predecessor_is_not_buffered_by_response_time_days():
    """The response time is a buffer after an arrival. The pieces of an
    in-house step are ready when it ends, so its end day gates the next
    step whatever the response time is."""
    lot = make_lot()
    predecessor_position = make_position(id=1, sequence=1)
    successor_position = make_position(id=2, sequence=2)
    lot.positions = [predecessor_position, successor_position]
    predecessor_order = make_order(id=10, lot_position_id=1)
    predecessor_order.planned_end = datetime(2026, 1, 10, 14, 0)
    successor_order = make_order(id=20, lot_position_id=2)
    repos = build_repos(orders=[predecessor_order, successor_order])

    unbuffered = await build_order_context(
        successor_order,
        lot,
        machine=None,
        repos=repos,
        target_date=None,
        response_time_days=0,
        zone=UTC,
    )
    buffered = await build_order_context(
        successor_order,
        lot,
        machine=None,
        repos=repos,
        target_date=None,
        response_time_days=3,
        zone=UTC,
    )

    assert unbuffered.predecessor_ready_at == date(2026, 1, 10)
    assert buffered.predecessor_ready_at == date(2026, 1, 10)


async def test_an_external_predecessor_is_buffered_by_response_time_days():
    lot = make_lot()
    predecessor_position = make_position(id=1, sequence=1)
    predecessor_position.kind = LotPositionKind.EXTERNAL
    successor_position = make_position(id=2, sequence=2)
    lot.positions = [predecessor_position, successor_position]
    delivered = make_order_item(30, delivery_date=date(2026, 1, 10))
    delivered.lot_position_id = 1
    successor_order = make_order(id=20, lot_position_id=2)
    repos = build_repos(orders=[successor_order], order_items=[delivered])

    unbuffered = await build_order_context(
        successor_order,
        lot,
        machine=None,
        repos=repos,
        target_date=None,
        response_time_days=0,
        zone=UTC,
    )
    buffered = await build_order_context(
        successor_order,
        lot,
        machine=None,
        repos=repos,
        target_date=None,
        response_time_days=3,
        zone=UTC,
    )

    assert unbuffered.predecessor_ready_at == date(2026, 1, 10)
    assert buffered.predecessor_ready_at == date(2026, 1, 13)


async def test_an_in_house_predecessor_hands_over_after_the_handoff_minutes():
    lot = make_lot()
    predecessor_position = make_position(id=1, sequence=1)
    successor_position = make_position(id=2, sequence=2)
    lot.positions = [predecessor_position, successor_position]
    predecessor_order = make_order(id=10, lot_position_id=1)
    predecessor_order.planned_end = datetime(2026, 1, 10, 14, 0, tzinfo=UTC)
    successor_order = make_order(id=20, lot_position_id=2)
    repos = build_repos(orders=[predecessor_order, successor_order])

    ctx = await build_order_context(
        successor_order,
        lot,
        machine=None,
        repos=repos,
        target_date=None,
        internal_handoff_minutes=45,
        zone=UTC,
    )

    assert ctx.internal_handoff_minutes == 45
    assert ctx.predecessor_ready_moment == datetime(2026, 1, 10, 14, 45, tzinfo=UTC)


async def test_material_ready_at_is_buffered_by_response_time_days():
    lot = make_lot(input_demand_id=99)
    position = make_position(id=1, sequence=1)
    lot.positions = [position]
    order = make_order(id=10, lot_position_id=1)
    demand = SourceItemDemandItem(
        id=99,
        created=date(2026, 1, 1),
        changed=None,
        changes=[],
        status=SourceItemDemandStatus.FULFILLED,
        quantity=10.0,
        unit="pcs",
        items_per_unit=1.0,
        high_priority=False,
        notify_on_delivery=False,
        note=None,
        desired_delivery_date=None,
        creator_id=1,
        bought_item_id=None,
        source_item_id=1,
        lot_id=1,
        project_id=1,
    )
    allocation = SourceItemDemandAllocation(demand_item_id=99, order_item_id=50, quantity=10.0)
    order_item = make_order_item(id=50, delivery_date=date(2026, 1, 5))
    repos = build_repos(
        orders=[order],
        order_items=[order_item],
        demand=demand,
        allocations=[allocation],
    )

    unbuffered = await build_order_context(
        order, lot, machine=None, repos=repos, target_date=None, response_time_days=0, zone=UTC
    )
    buffered = await build_order_context(
        order, lot, machine=None, repos=repos, target_date=None, response_time_days=2, zone=UTC
    )

    assert unbuffered.material_ready_at == date(2026, 1, 5)
    assert buffered.material_ready_at == date(2026, 1, 7)


async def test_not_before_is_never_buffered():
    lot = make_lot()
    position = make_position(id=1, sequence=1)
    lot.positions = [position]
    order = make_order(id=10, lot_position_id=1, not_before=date(2026, 1, 1))
    repos = build_repos(orders=[order])

    ctx = await build_order_context(
        order, lot, machine=None, repos=repos, target_date=None, response_time_days=5, zone=UTC
    )

    assert ctx.not_before == date(2026, 1, 1)


async def test_no_ready_at_date_stays_none_regardless_of_buffer():
    """A first position with no material demand at all (make-to-stock)
    has nothing to buffer: the buffer only shifts a date that's
    already known, never manufactures a constraint from nothing."""
    lot = make_lot(input_demand_id=None)
    position = make_position(id=1, sequence=1)
    lot.positions = [position]
    order = make_order(id=10, lot_position_id=1)
    repos = build_repos(orders=[order])

    ctx = await build_order_context(
        order, lot, machine=None, repos=repos, target_date=None, response_time_days=5, zone=UTC
    )

    assert ctx.material_ready_at is None
    assert ctx.predecessor_ready_at is None
