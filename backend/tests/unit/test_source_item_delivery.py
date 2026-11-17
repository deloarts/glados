"""
Unit tests for the source item demands a delivery on a SOURCE line settles
through ProcessOrderItemDelivery. No database, no HTTP. All dependencies are
in-memory fakes, and the lifecycle reconciler reads the source demand and
allocation fakes, so each demand shows the status its derivation gives: a
demand fully covered by a placed line is ordered until the deliveries cover
it, then fulfilled.
"""

from datetime import UTC
from datetime import date
from datetime import datetime
from typing import Any

from src.modules.fulfillment.application.use_cases.order.process_order_item_delivery import (
    ProcessOrderItemDelivery,
)
from src.modules.fulfillment.domain.entities.bought_item_allocation import (
    BoughtItemDemandAllocation,
)
from src.modules.fulfillment.domain.entities.bought_item_demand_item import BoughtItemDemandItem
from src.modules.fulfillment.domain.entities.order import Order
from src.modules.fulfillment.domain.entities.order_item import OrderItem
from src.modules.fulfillment.domain.entities.order_item_delivery import OrderItemDelivery
from src.modules.fulfillment.domain.entities.source_item_allocation import (
    SourceItemDemandAllocation,
)
from src.modules.fulfillment.domain.entities.source_item_demand_item import SourceItemDemandItem
from src.modules.fulfillment.domain.value_objects.order_status import OrderItemStatus
from src.modules.fulfillment.domain.value_objects.order_status import OrderLineType
from src.modules.fulfillment.domain.value_objects.order_status import OrderStatus
from src.modules.fulfillment.domain.value_objects.source_item_demand_status import (
    SourceItemDemandStatus,
)
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.value_objects.permission import Permission
from tests import factories
from tests.unit.lifecycle.fake_demand_reconciler import demand_reconciler
from tests.unit.lifecycle.fake_reconciler import order_reconciler
from tests.unit.production_lot._helpers import NoLotCreation
from tests.unit.production_lot.fakes import FakeMadeItemAllocationRepository
from tests.unit.production_lot.fakes import FakeMadeItemDemandRepository
from tests.unit.production_lot.fakes import delivery_collaborators

# ── Helpers ───────────────────────────────────────────────────────────


def make_user(*, permissions: list[str] | None = None, **overrides: Any) -> User:
    """A user who may receive deliveries unless the test passes other permissions."""
    if permissions is None:
        permissions = [Permission.RECEIVE_DELIVERIES]
    return factories.make_user(permissions=permissions, **overrides)


def make_order_item(
    id: int = 1,
    order_id: int = 1,
    quantity: float = 10.0,
    quantity_delivered: float = 0.0,
    status: OrderItemStatus = OrderItemStatus.ORDERED,
    source_item_id: int | None = 1,
) -> OrderItem:
    return OrderItem(
        id=id,
        created=date(2026, 1, 1),
        changed=None,
        changes=[],
        status=status,
        quantity=quantity,
        quantity_delivered=quantity_delivered,
        unit="pcs",
        items_per_unit=1.0,
        price=None,
        note=None,
        ordered_date=date(2026, 1, 1),
        expected_delivery_date=None,
        delivery_date=None,
        storage_place=None,
        expected_pickup_date=None,
        ready_for_pickup_date=None,
        position=1,
        creator_id=1,
        orderer_id=None,
        receiver_id=None,
        bought_item_id=None,
        order_id=order_id,
        supplier_id=1,
        project_id=1,
        line_type=OrderLineType.SOURCE,
        lot_position_id=None,
        source_item_id=source_item_id,
    )


def make_order(id: int = 1, status: OrderStatus = OrderStatus.ORDERED) -> Order:
    return Order(
        id=id,
        order_number="ORD-2026-0001",
        created=date(2026, 1, 1),
        changed=None,
        changes=[],
        status=status,
        note=None,
        ordered_date=date(2026, 1, 1),
        expected_delivery_date=None,
        delivery_date=None,
        storage_place=None,
        creator_id=1,
        supplier_id=1,
    )


def make_base_demand(
    id: int = 1,
    quantity: float = 10.0,
    status: SourceItemDemandStatus = SourceItemDemandStatus.ALLOCATED,
    lot_id: int = 1,
) -> SourceItemDemandItem:
    return SourceItemDemandItem(
        id=id,
        created=date(2026, 1, 1),
        changed=None,
        changes=[],
        status=status,
        quantity=quantity,
        unit="pcs",
        items_per_unit=1.0,
        high_priority=False,
        notify_on_delivery=False,
        note=None,
        desired_delivery_date=None,
        creator_id=1,
        bought_item_id=None,
        source_item_id=1,
        lot_id=lot_id,
        project_id=1,
    )


class FakeOrderItemRepository:
    def __init__(self, items: list[OrderItem] | None = None):
        self._items: dict[int, OrderItem] = {i.id: i for i in (items or [])}

    async def get_by_ids(self, ids: list[int], *, refresh: bool = False) -> list:
        found = [await self.get_by_id(i) for i in ids]
        return [item for item in found if item is not None]

    async def get_by_id(self, id: int):
        return self._items.get(id)

    async def get_by_id_for_update(self, id: int):
        return self._items.get(id)

    async def get_by_order_id(self, order_id: int):
        return [i for i in self._items.values() if i.order_id == order_id]

    async def get_by_order_ids(self, order_ids: list[int], *, refresh: bool = False):
        return [i for i in self._items.values() if i.order_id in order_ids]

    async def get_by_bought_item_id(self, bought_item_id: int):
        return [i for i in self._items.values() if i.bought_item_id == bought_item_id]

    async def get_by_source_item_id(self, source_item_id: int):
        return [i for i in self._items.values() if i.source_item_id == source_item_id]

    async def save(self, item: OrderItem) -> OrderItem:
        self._items[item.id] = item
        return item

    async def delete(self, item: OrderItem) -> None:
        self._items.pop(item.id, None)


class FakeOrderRepository:
    def __init__(self, orders: list[Order] | None = None):
        self._orders: dict[int, Order] = {o.id: o for o in (orders or [])}

    async def get_by_id(self, id: int):
        return self._orders.get(id)

    async def save(self, order: Order) -> Order:
        self._orders[order.id] = order
        return order


class FakeBoughtAllocationRepository:
    """Empty stand-in, these tests only exercise the source-item cascade."""

    def __init__(self):
        self._allocations: list[BoughtItemDemandAllocation] = []

    async def get_by_demand_item_id(self, demand_item_id: int):
        return []

    async def get_by_order_item_id(self, order_item_id: int):
        return []


class FakeBoughtDemandRepository:
    def __init__(self):
        self._demands: dict[int, BoughtItemDemandItem] = {}

    async def get_by_id(self, id: int):
        return self._demands.get(id)

    async def get_by_id_for_update(self, id: int):
        return self._demands.get(id)

    async def save(self, demand):
        self._demands[demand.id] = demand
        return demand


class FakeSourceItemDemandRepository:
    def __init__(self, demands: list[SourceItemDemandItem] | None = None):
        self._demands: dict[int, SourceItemDemandItem] = {d.id: d for d in (demands or [])}

    async def get_by_id(self, id: int):
        return self._demands.get(id)

    async def get_by_id_for_update(self, id: int):
        return self._demands.get(id)

    async def save(self, demand: SourceItemDemandItem) -> SourceItemDemandItem:
        self._demands[demand.id] = demand
        return demand


class FakeSourceItemAllocationRepository:
    def __init__(self, allocations: list[SourceItemDemandAllocation] | None = None):
        self._allocations: list[SourceItemDemandAllocation] = list(allocations or [])

    async def get_by_demand_item_id(self, demand_item_id: int):
        return [a for a in self._allocations if a.demand_item_id == demand_item_id]

    async def get_by_order_item_id(self, order_item_id: int):
        return [a for a in self._allocations if a.order_item_id == order_item_id]


class FakeDeliveryRepository:
    def __init__(self):
        self._deliveries: list[OrderItemDelivery] = []
        self._next_id = 1

    async def get_by_order_item_id(self, order_item_id: int):
        return [d for d in self._deliveries if d.order_item_id == order_item_id]

    async def get_by_order_item_ids(self, order_item_ids: list[int]):
        return [d for d in self._deliveries if d.order_item_id in order_item_ids]

    async def save(self, delivery: OrderItemDelivery) -> OrderItemDelivery:
        delivery.id = self._next_id
        self._next_id += 1
        self._deliveries.append(delivery)
        return delivery


class FakeEventBus:
    def __init__(self):
        self.published = []

    async def publish(self, event):
        self.published.append(event)


class FakeUnitOfWork:
    def __init__(self):
        self.committed = False

    async def commit(self):
        self.committed = True

    async def rollback(self):
        pass


# ── Source-item delivery cascade ────────────────────────────────────────


class TestSourceItemDeliveryCascade:
    def setup_method(self):
        self.actor = make_user()
        self.order = make_order(id=1)
        self.order_repo = FakeOrderRepository([self.order])
        self.bought_allocations = FakeBoughtAllocationRepository()
        self.bought_demands = FakeBoughtDemandRepository()
        self.delivery_repo = FakeDeliveryRepository()
        self.bus = FakeEventBus()

    def _use_case(
        self,
        order_item_repo: FakeOrderItemRepository,
        source_item_demands: FakeSourceItemDemandRepository,
        source_item_allocations: FakeSourceItemAllocationRepository,
    ) -> ProcessOrderItemDelivery:
        self.uow = FakeUnitOfWork()
        return ProcessOrderItemDelivery(
            order_item_repo=order_item_repo,
            order_repo=self.order_repo,
            delivery_repo=self.delivery_repo,
            event_bus=self.bus,
            uow=self.uow,
            reconciler=demand_reconciler(
                source_demands=source_item_demands,
                source_allocations=source_item_allocations,
                orders=self.order_repo,
                order_items=order_item_repo,
            ),
            made_item_demand_repo=FakeMadeItemDemandRepository(),
            made_item_allocation_repo=FakeMadeItemAllocationRepository(),
            create_lot=NoLotCreation(),
            **delivery_collaborators(
                source_item_demand_repo=source_item_demands,
                source_item_allocation_repo=source_item_allocations,
                bought_item_allocation_repo=self.bought_allocations,
            ),
        )

    async def test_full_delivery_fulfills_single_demand(self):
        order_item = make_order_item(id=1, quantity=10.0)
        order_items = FakeOrderItemRepository([order_item])
        demand = make_base_demand(id=1, quantity=10.0)
        demands = FakeSourceItemDemandRepository([demand])
        allocations = FakeSourceItemAllocationRepository(
            [SourceItemDemandAllocation(demand_item_id=1, order_item_id=1, quantity=10.0)]
        )
        use_case = self._use_case(order_items, demands, allocations)

        await use_case.execute(actor=self.actor, order_item_id=1, quantity=10.0)

        assert (await demands.get_by_id(1)).status == SourceItemDemandStatus.FULFILLED.value

    async def test_partial_delivery_keeps_demand_ordered(self):
        order_item = make_order_item(id=1, quantity=10.0)
        order_items = FakeOrderItemRepository([order_item])
        demand = make_base_demand(id=1, quantity=10.0)
        demands = FakeSourceItemDemandRepository([demand])
        allocations = FakeSourceItemAllocationRepository(
            [SourceItemDemandAllocation(demand_item_id=1, order_item_id=1, quantity=10.0)]
        )
        use_case = self._use_case(order_items, demands, allocations)

        await use_case.execute(actor=self.actor, order_item_id=1, quantity=4.0)

        assert (await demands.get_by_id(1)).status == SourceItemDemandStatus.ORDERED.value

    async def test_shared_bulk_order_item_fills_its_demands_in_order(self):
        """One bulk order item covers two demands from two different lots; a
        partial delivery fills them in order, the older demand first, so the
        first pieces that arrive fulfill one demand instead of leaving both
        short by the same ratio."""
        order_item = make_order_item(id=1, quantity=20.0)
        order_items = FakeOrderItemRepository([order_item])
        small_demand = make_base_demand(id=1, quantity=4.0, lot_id=1)
        large_demand = make_base_demand(id=2, quantity=16.0, lot_id=2)
        demands = FakeSourceItemDemandRepository([small_demand, large_demand])
        allocations = FakeSourceItemAllocationRepository(
            [
                SourceItemDemandAllocation(demand_item_id=1, order_item_id=1, quantity=4.0),
                SourceItemDemandAllocation(demand_item_id=2, order_item_id=1, quantity=16.0),
            ]
        )
        use_case = self._use_case(order_items, demands, allocations)

        # Deliver 5 of 20: the small demand takes its 4, the large one the
        # remaining 1.
        await use_case.execute(actor=self.actor, order_item_id=1, quantity=5.0)

        assert (await demands.get_by_id(1)).status == SourceItemDemandStatus.FULFILLED.value
        assert (await demands.get_by_id(2)).status == SourceItemDemandStatus.ORDERED.value

        # Deliver the remaining 15 (order item now fully delivered) -> both
        # demands' full allocated quantity now counts as delivered.
        await use_case.execute(actor=self.actor, order_item_id=1, quantity=15.0)

        assert (await demands.get_by_id(1)).status == SourceItemDemandStatus.FULFILLED.value
        assert (await demands.get_by_id(2)).status == SourceItemDemandStatus.FULFILLED.value

    async def test_terminal_demand_is_not_touched(self):
        order_item = make_order_item(id=1, quantity=10.0)
        order_items = FakeOrderItemRepository([order_item])
        demand = make_base_demand(id=1, quantity=10.0, status=SourceItemDemandStatus.CANCELED)
        demand.canceled_at = datetime(2026, 1, 2, tzinfo=UTC)
        demands = FakeSourceItemDemandRepository([demand])
        allocations = FakeSourceItemAllocationRepository(
            [SourceItemDemandAllocation(demand_item_id=1, order_item_id=1, quantity=10.0)]
        )
        use_case = self._use_case(order_items, demands, allocations)

        await use_case.execute(actor=self.actor, order_item_id=1, quantity=10.0)

        assert (await demands.get_by_id(1)).status == SourceItemDemandStatus.CANCELED.value

    async def test_bought_line_delivery_runs_no_source_cascade(self):
        """A bought line's delivery leaves the source demands alone and
        completes the line without any source demand to cascade to."""
        order_item = make_order_item(id=1, quantity=10.0, source_item_id=None)
        order_item.line_type = OrderLineType.BOUGHT
        order_item.bought_item_id = 1
        order_items = FakeOrderItemRepository([order_item])
        self.uow = FakeUnitOfWork()
        use_case = ProcessOrderItemDelivery(
            order_item_repo=order_items,
            order_repo=self.order_repo,
            delivery_repo=self.delivery_repo,
            event_bus=self.bus,
            uow=self.uow,
            reconciler=order_reconciler(self.order_repo, order_items),
            made_item_demand_repo=FakeMadeItemDemandRepository(),
            made_item_allocation_repo=FakeMadeItemAllocationRepository(),
            create_lot=NoLotCreation(),
            **delivery_collaborators(),
        )

        result = await use_case.execute(actor=self.actor, order_item_id=1, quantity=10.0)
        assert result.status == "delivered"
