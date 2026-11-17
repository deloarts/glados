"""
Unit tests for partial delivery of bought item order items.
No database, no HTTP. All dependencies replaced with in-memory fakes.
"""

from datetime import UTC
from datetime import date
from datetime import datetime
from typing import Any

import pytest

from src.modules.catalogue.domain.value_objects.bought_item_status import BoughtItemDemandStatus
from src.modules.fulfillment.application.use_cases.order.process_order_item_delivery import (
    DeliverAllOrderItems,
)
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
from src.modules.fulfillment.domain.errors import InvalidDeliveryQuantityError
from src.modules.fulfillment.domain.services.allocation_service import AllocationQuantityService
from src.modules.fulfillment.domain.value_objects.order_status import OrderItemStatus
from src.modules.fulfillment.domain.value_objects.order_status import OrderLineType
from src.modules.fulfillment.domain.value_objects.order_status import OrderStatus
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.exceptions import InsufficientPermissionsError
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
        bought_item_id=1,
        order_id=order_id,
        supplier_id=1,
        project_id=1,
        line_type=OrderLineType.BOUGHT,
        lot_position_id=None,
        source_item_id=None,
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


def make_demand(
    id: int = 1,
    quantity: float = 10.0,
    status: BoughtItemDemandStatus = BoughtItemDemandStatus.ALLOCATED,
) -> BoughtItemDemandItem:
    return BoughtItemDemandItem(
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
        item_id=1,
        project_id=1,
    )


class FakeOrderItemRepository:
    def __init__(self, items: list[OrderItem] | None = None):
        self._items: dict[int, OrderItem] = {i.id: i for i in (items or [])}
        self.for_update_calls: list[int] = []

    async def get_by_ids(self, ids: list[int], *, refresh: bool = False) -> list:
        found = [await self.get_by_id(i) for i in ids]
        return [item for item in found if item is not None]

    async def get_by_id(self, id: int):
        return self._items.get(id)

    async def get_by_id_for_update(self, id: int):
        self.for_update_calls.append(id)
        return self._items.get(id)

    async def get_by_order_id(self, order_id: int):
        return [i for i in self._items.values() if i.order_id == order_id]

    async def get_by_order_ids(self, order_ids: list[int], *, refresh: bool = False):
        return [i for i in self._items.values() if i.order_id in order_ids]

    async def get_by_bought_item_id(self, bought_item_id: int):
        return [i for i in self._items.values() if i.bought_item_id == bought_item_id]

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


class FakeAllocationRepository:
    def __init__(self, allocations: list[BoughtItemDemandAllocation] | None = None):
        self._allocations = list(allocations or [])

    async def get_by_demand_item_id(self, demand_item_id: int):
        return [a for a in self._allocations if a.demand_item_id == demand_item_id]

    async def get_by_order_item_id(self, order_item_id: int):
        return [a for a in self._allocations if a.order_item_id == order_item_id]


class FakeDemandRepository:
    def __init__(self, demands: list[BoughtItemDemandItem] | None = None):
        self._demands: dict[int, BoughtItemDemandItem] = {d.id: d for d in (demands or [])}

    async def get_by_id(self, id: int):
        return self._demands.get(id)

    async def get_by_id_for_update(self, id: int):
        return self._demands.get(id)

    async def save(self, demand: BoughtItemDemandItem) -> BoughtItemDemandItem:
        self._demands[demand.id] = demand
        return demand


class FakeDeliveryRepository:
    def __init__(self):
        self._deliveries: list[OrderItemDelivery] = []
        self._next_id = 1

    @property
    def deliveries(self) -> list[OrderItemDelivery]:
        """The stored deliveries, for assertions."""
        return self._deliveries

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
        self.rolled_back = False

    async def commit(self):
        self.committed = True

    async def rollback(self):
        self.rolled_back = True


class FakeRecomputeSchedule:
    """Fake for the single execute_all() call, see
    tests/unit/production_order/fakes.py's identical class."""

    def __init__(self) -> None:
        self.execute_all_calls: int = 0

    async def execute_all(self, response_time_days=None, settings=None):
        self.execute_all_calls += 1
        return []


class FailingRecomputeSchedule:
    def __init__(self) -> None:
        self.attempts: int = 0

    async def execute_all(self, response_time_days=None, settings=None):
        self.attempts += 1
        raise RuntimeError("scheduling service is down")


# ── ProcessOrderItemDelivery tests ──────────────────────────────────────


class TestProcessOrderItemDelivery:
    def setup_method(self):
        self.actor = make_user()
        self.order_item = make_order_item(id=1, order_id=1, quantity=10.0)
        self.order = make_order(id=1)
        self.order_item_repo = FakeOrderItemRepository([self.order_item])
        self.order_repo = FakeOrderRepository([self.order])
        self.allocation_repo = FakeAllocationRepository()
        self.demand_repo = FakeDemandRepository()
        self.delivery_repo = FakeDeliveryRepository()
        self.bus = FakeEventBus()
        self.uow = FakeUnitOfWork()
        self.use_case = ProcessOrderItemDelivery(
            order_item_repo=self.order_item_repo,
            order_repo=self.order_repo,
            delivery_repo=self.delivery_repo,
            event_bus=self.bus,
            uow=self.uow,
            reconciler=demand_reconciler(
                orders=self.order_repo,
                order_items=self.order_item_repo,
                bought_demands=self.demand_repo,
                bought_allocations=self.allocation_repo,
            ),
            made_item_demand_repo=FakeMadeItemDemandRepository(),
            made_item_allocation_repo=FakeMadeItemAllocationRepository(),
            create_lot=NoLotCreation(),
            **delivery_collaborators(bought_item_allocation_repo=self.allocation_repo),
        )

    async def test_partial_delivery_sets_status_partially_delivered(self):
        result = await self.use_case.execute(
            actor=self.actor, order_item_id=1, quantity=2.0, storage_place="A1"
        )
        assert result.status == "partially_delivered"
        assert result.quantity_delivered == 2.0
        records = await self.delivery_repo.get_by_order_item_id(1)
        assert len(records) == 1
        assert records[0].quantity == 2.0
        assert records[0].storage_place == "A1"
        assert records[0].receiver_id == self.actor.id

    async def test_a_booking_without_a_storage_place_keeps_the_lines(self):
        await self.use_case.execute(
            actor=self.actor, order_item_id=1, quantity=2.0, storage_place="A1"
        )

        result = await self.use_case.execute(
            actor=self.actor, order_item_id=1, quantity=1.0, storage_place=None
        )

        assert result.storage_place == "A1"
        records = await self.delivery_repo.get_by_order_item_id(1)
        assert [r.storage_place for r in records] == ["A1", "A1"]

    async def test_a_new_storage_place_replaces_the_lines(self):
        await self.use_case.execute(
            actor=self.actor, order_item_id=1, quantity=2.0, storage_place="A1"
        )

        result = await self.use_case.execute(
            actor=self.actor, order_item_id=1, quantity=1.0, storage_place="B2"
        )

        assert result.storage_place == "B2"

    async def test_reads_the_order_item_with_a_row_lock(self):
        """Two concurrent deliveries of the same item must not both
        read the pre-write quantity, see
        IOrderItemRepository.get_by_id_for_update."""
        await self.use_case.execute(actor=self.actor, order_item_id=1, quantity=2.0)
        assert self.order_item_repo.for_update_calls == [1]

    async def test_second_delivery_completes_item(self):
        await self.use_case.execute(actor=self.actor, order_item_id=1, quantity=2.0)
        result = await self.use_case.execute(actor=self.actor, order_item_id=1, quantity=8.0)
        assert result.status == "delivered"
        assert result.quantity_delivered == 10.0
        assert len(await self.delivery_repo.get_by_order_item_id(1)) == 2

    async def test_omitted_quantity_delivers_remaining(self):
        await self.use_case.execute(actor=self.actor, order_item_id=1, quantity=3.0)
        result = await self.use_case.execute(actor=self.actor, order_item_id=1)
        assert result.status == "delivered"
        assert result.quantity_delivered == 10.0

    async def test_overdelivery_raises(self):
        with pytest.raises(InvalidDeliveryQuantityError):
            await self.use_case.execute(actor=self.actor, order_item_id=1, quantity=11.0)

    async def test_zero_quantity_raises(self):
        with pytest.raises(InvalidDeliveryQuantityError):
            await self.use_case.execute(actor=self.actor, order_item_id=1, quantity=0.0)

    async def test_negative_quantity_raises(self):
        with pytest.raises(InvalidDeliveryQuantityError):
            await self.use_case.execute(actor=self.actor, order_item_id=1, quantity=-1.0)

    async def test_order_status_rolls_up_to_partially_delivered(self):
        await self.use_case.execute(actor=self.actor, order_item_id=1, quantity=2.0)
        order = await self.order_repo.get_by_id(1)
        assert order.status == "partially_delivered"

    async def test_order_status_rolls_up_to_delivered_when_fully_delivered(self):
        await self.use_case.execute(actor=self.actor, order_item_id=1, quantity=10.0)
        order = await self.order_repo.get_by_id(1)
        assert order.status == "delivered"
        # Full UTC instant, not just the day, see Order.delivery_date.
        assert order.delivery_date.tzinfo is not None
        assert order.delivery_date.date() == datetime.now(UTC).date()

    async def test_demand_fulfillment_is_proportional_to_partial_delivery(self):
        demand = make_demand(id=1, quantity=10.0)
        allocation = BoughtItemDemandAllocation(demand_item_id=1, order_item_id=1, quantity=10.0)
        self.allocation_repo = FakeAllocationRepository([allocation])
        self.demand_repo = FakeDemandRepository([demand])
        self.uow = FakeUnitOfWork()
        self.use_case = ProcessOrderItemDelivery(
            order_item_repo=self.order_item_repo,
            order_repo=self.order_repo,
            delivery_repo=self.delivery_repo,
            event_bus=self.bus,
            uow=self.uow,
            reconciler=demand_reconciler(
                orders=self.order_repo,
                order_items=self.order_item_repo,
                bought_demands=self.demand_repo,
                bought_allocations=self.allocation_repo,
            ),
            made_item_demand_repo=FakeMadeItemDemandRepository(),
            made_item_allocation_repo=FakeMadeItemAllocationRepository(),
            create_lot=NoLotCreation(),
            **delivery_collaborators(bought_item_allocation_repo=self.allocation_repo),
        )

        await self.use_case.execute(actor=self.actor, order_item_id=1, quantity=2.0)
        demand_after_partial = await self.demand_repo.get_by_id(1)
        # Fully covered by a placed line and not yet fulfilled.
        assert demand_after_partial.status == "ordered"

        await self.use_case.execute(actor=self.actor, order_item_id=1, quantity=8.0)
        demand_after_full = await self.demand_repo.get_by_id(1)
        assert demand_after_full.status == "fulfilled"

    async def test_fractional_deliveries_that_sum_to_the_quantity_fulfil_the_demand(self):
        """Ten deliveries of 0.1 m add up to 0.9999999999999999 in floating
        point. The derivation compares within the shared quantity tolerance,
        so the demand they cover in full is fulfilled all the same."""
        line = make_order_item(id=1, quantity=1.0)
        line.unit = "M"
        self.order_item_repo = FakeOrderItemRepository([line])
        self.demand_repo = FakeDemandRepository([make_demand(id=1, quantity=1.0)])
        self.allocation_repo = FakeAllocationRepository(
            [BoughtItemDemandAllocation(demand_item_id=1, order_item_id=1, quantity=1.0)]
        )
        self.use_case = ProcessOrderItemDelivery(
            order_item_repo=self.order_item_repo,
            order_repo=self.order_repo,
            delivery_repo=self.delivery_repo,
            event_bus=self.bus,
            uow=self.uow,
            reconciler=demand_reconciler(
                orders=self.order_repo,
                order_items=self.order_item_repo,
                bought_demands=self.demand_repo,
                bought_allocations=self.allocation_repo,
            ),
            made_item_demand_repo=FakeMadeItemDemandRepository(),
            made_item_allocation_repo=FakeMadeItemAllocationRepository(),
            create_lot=NoLotCreation(),
            **delivery_collaborators(bought_item_allocation_repo=self.allocation_repo),
        )

        for _ in range(10):
            await self.use_case.execute(actor=self.actor, order_item_id=1, quantity=0.1)

        line = await self.order_item_repo.get_by_id(1)
        assert line.quantity_delivered < 1.0
        assert (await self.demand_repo.get_by_id(1)).status == "fulfilled"

    async def test_recompute_is_called_exactly_once_on_success(self):
        recompute = FakeRecomputeSchedule()
        use_case = ProcessOrderItemDelivery(
            order_item_repo=self.order_item_repo,
            order_repo=self.order_repo,
            delivery_repo=self.delivery_repo,
            recompute_schedule=recompute,
            event_bus=self.bus,
            uow=self.uow,
            reconciler=demand_reconciler(
                orders=self.order_repo,
                order_items=self.order_item_repo,
                bought_demands=self.demand_repo,
                bought_allocations=self.allocation_repo,
            ),
            made_item_demand_repo=FakeMadeItemDemandRepository(),
            made_item_allocation_repo=FakeMadeItemAllocationRepository(),
            create_lot=NoLotCreation(),
            **delivery_collaborators(bought_item_allocation_repo=self.allocation_repo),
        )
        await use_case.execute(actor=self.actor, order_item_id=1, quantity=2.0)
        assert recompute.execute_all_calls == 1

    async def test_recompute_failure_does_not_roll_back_the_commit(self):
        recompute = FailingRecomputeSchedule()
        use_case = ProcessOrderItemDelivery(
            order_item_repo=self.order_item_repo,
            order_repo=self.order_repo,
            delivery_repo=self.delivery_repo,
            recompute_schedule=recompute,
            event_bus=self.bus,
            uow=self.uow,
            reconciler=demand_reconciler(
                orders=self.order_repo,
                order_items=self.order_item_repo,
                bought_demands=self.demand_repo,
                bought_allocations=self.allocation_repo,
            ),
            made_item_demand_repo=FakeMadeItemDemandRepository(),
            made_item_allocation_repo=FakeMadeItemAllocationRepository(),
            create_lot=NoLotCreation(),
            **delivery_collaborators(bought_item_allocation_repo=self.allocation_repo),
        )
        result = await use_case.execute(actor=self.actor, order_item_id=1, quantity=2.0)
        assert recompute.attempts == 1
        assert result.status == "partially_delivered"
        assert self.uow.committed is True


# ── ProcessOrderItemDelivery / DeliverAllOrderItems permission gate ─────


class TestProcessOrderItemDeliveryPermissions:
    """receive:deliveries is deliberately separate from write:orders/
    manage:orders, see OrderRules.assert_can_receive_delivery. These tests
    cover the gate itself, independent of the delivery mechanics already
    covered above."""

    def setup_method(self):
        self.order_item = make_order_item(id=1, order_id=1, quantity=10.0)
        self.order = make_order(id=1)
        self.order_item_repo = FakeOrderItemRepository([self.order_item])
        self.order_repo = FakeOrderRepository([self.order])
        self.allocation_repo = FakeAllocationRepository()
        self.demand_repo = FakeDemandRepository()
        self.delivery_repo = FakeDeliveryRepository()
        self.bus = FakeEventBus()
        self.uow = FakeUnitOfWork()
        self.use_case = ProcessOrderItemDelivery(
            order_item_repo=self.order_item_repo,
            order_repo=self.order_repo,
            delivery_repo=self.delivery_repo,
            event_bus=self.bus,
            uow=self.uow,
            reconciler=demand_reconciler(
                orders=self.order_repo,
                order_items=self.order_item_repo,
                bought_demands=self.demand_repo,
                bought_allocations=self.allocation_repo,
            ),
            made_item_demand_repo=FakeMadeItemDemandRepository(),
            made_item_allocation_repo=FakeMadeItemAllocationRepository(),
            create_lot=NoLotCreation(),
            **delivery_collaborators(bought_item_allocation_repo=self.allocation_repo),
        )

    async def test_actor_without_permission_is_rejected(self):
        actor = make_user(permissions=[])
        with pytest.raises(InsufficientPermissionsError):
            await self.use_case.execute(actor=actor, order_item_id=1, quantity=2.0)
        # No partial write should have happened before the rejection.
        assert self.order_item.quantity_delivered == 0.0
        assert await self.delivery_repo.get_by_order_item_id(1) == []
        assert self.uow.committed is False

    async def test_actor_with_write_orders_but_not_receive_deliveries_is_rejected(self):
        """write:orders alone must not be enough, that would make the new
        permission redundant instead of a genuine separation of duties."""
        actor = make_user(permissions=[Permission.WRITE_ORDERS, Permission.MANAGE_ORDERS])
        with pytest.raises(InsufficientPermissionsError):
            await self.use_case.execute(actor=actor, order_item_id=1, quantity=2.0)

    async def test_actor_with_permission_succeeds(self):
        actor = make_user(permissions=[Permission.RECEIVE_DELIVERIES])
        result = await self.use_case.execute(actor=actor, order_item_id=1, quantity=2.0)
        assert result.quantity_delivered == 2.0

    async def test_systemuser_bypasses_the_check(self):
        actor = make_user(permissions=[], is_systemuser=True)
        result = await self.use_case.execute(actor=actor, order_item_id=1, quantity=2.0)
        assert result.quantity_delivered == 2.0


class TestDeliverAllOrderItemsPermissions:
    def setup_method(self):
        self.order_item = make_order_item(id=1, order_id=1, quantity=10.0)
        self.order = make_order(id=1)
        self.order_item_repo = FakeOrderItemRepository([self.order_item])
        self.order_repo = FakeOrderRepository([self.order])
        self.allocation_repo = FakeAllocationRepository()
        self.demand_repo = FakeDemandRepository()
        self.delivery_repo = FakeDeliveryRepository()
        self.bus = FakeEventBus()
        self.uow = FakeUnitOfWork()
        # One reconciler per request, shared by both use cases.
        reconciler = order_reconciler(self.order_repo, self.order_item_repo)
        self.deliver_one = ProcessOrderItemDelivery(
            order_item_repo=self.order_item_repo,
            order_repo=self.order_repo,
            delivery_repo=self.delivery_repo,
            event_bus=self.bus,
            uow=self.uow,
            reconciler=reconciler,
            made_item_demand_repo=FakeMadeItemDemandRepository(),
            made_item_allocation_repo=FakeMadeItemAllocationRepository(),
            create_lot=NoLotCreation(),
            **delivery_collaborators(bought_item_allocation_repo=self.allocation_repo),
        )
        self.use_case = DeliverAllOrderItems(
            order_repo=self.order_repo,
            order_item_repo=self.order_item_repo,
            delivery_use_case=self.deliver_one,
            event_bus=self.bus,
            uow=self.uow,
            reconciler=reconciler,
        )

    async def test_actor_without_permission_is_rejected_before_any_item_is_touched(self):
        actor = make_user(permissions=[])
        with pytest.raises(InsufficientPermissionsError):
            await self.use_case.execute(actor=actor, order_id=1)
        # Fails before the per-item loop starts, nothing delivered.
        assert self.order_item.quantity_delivered == 0.0
        assert self.uow.committed is False

    async def test_actor_with_permission_succeeds(self):
        actor = make_user(permissions=[Permission.RECEIVE_DELIVERIES])
        result = await self.use_case.execute(actor=actor, order_id=1)
        assert len(result.delivered) == 1
        assert result.delivered[0].quantity_delivered == 10.0


# ── AllocationQuantityService.compute_summary proportional delivery ────


class TestComputeSummaryFillsTheAllocations:
    def test_delivered_counts_the_pieces_that_arrived(self):
        demand = make_demand(id=1, quantity=10.0)
        order_item = make_order_item(id=1, quantity=10.0, quantity_delivered=4.0)
        allocation = BoughtItemDemandAllocation(demand_item_id=1, order_item_id=1, quantity=10.0)

        summary = AllocationQuantityService.compute_summary(
            demand, [allocation], {1: order_item}, fill={}
        )
        assert summary.delivered == 4.0
        assert summary.remaining == 6.0

    def test_a_demand_on_a_line_with_surplus_takes_its_pieces_first(self):
        # A line of 10 for a demand of 4 that received 5: the demand's 4
        # arrived, the surplus waits for no demand.
        demand = make_demand(id=1, quantity=4.0)
        order_item = make_order_item(id=1, quantity=10.0, quantity_delivered=5.0)
        allocation = BoughtItemDemandAllocation(demand_item_id=1, order_item_id=1, quantity=4.0)

        summary = AllocationQuantityService.compute_summary(
            demand, [allocation], {1: order_item}, fill={}
        )
        assert summary.delivered == 4.0

    def test_an_older_demand_on_the_line_is_filled_first(self):
        demand = make_demand(id=2, quantity=4.0)
        order_item = make_order_item(id=1, quantity=10.0, quantity_delivered=5.0)
        allocation = BoughtItemDemandAllocation(demand_item_id=2, order_item_id=1, quantity=4.0)
        fill = {1: [(0, 1, 6.0), (0, 2, 4.0)]}

        summary = AllocationQuantityService.compute_summary(
            demand, [allocation], {1: order_item}, fill
        )
        # Demand #1 takes the first 5; nothing reached demand #2 yet.
        assert summary.delivered == 0.0

    def test_fully_delivered_order_item_counts_allocation_in_full(self):
        demand = make_demand(id=1, quantity=10.0)
        order_item = make_order_item(
            id=1, quantity=10.0, quantity_delivered=10.0, status=OrderItemStatus.DELIVERED
        )
        allocation = BoughtItemDemandAllocation(demand_item_id=1, order_item_id=1, quantity=10.0)

        summary = AllocationQuantityService.compute_summary(
            demand, [allocation], {1: order_item}, fill={}
        )
        assert summary.delivered == 10.0
        assert summary.is_fully_delivered
