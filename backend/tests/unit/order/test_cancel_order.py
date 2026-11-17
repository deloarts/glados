"""
Unit tests for CancelOrder: which orders may be canceled and by whom, how
cancellation releases the allocations of undelivered lines while keeping
delivered ones, its event, and the schedule recompute that runs after the
commit. No database, no HTTP; every dependency is an in-memory fake.
"""

import pytest

from src.modules.catalogue.domain.value_objects.bought_item_status import BoughtItemDemandStatus
from src.modules.fulfillment.application.use_cases.order.update_order import CancelOrder
from src.modules.fulfillment.domain.errors import OrderCannotBeCanceledError
from src.modules.fulfillment.domain.errors import OrderNotFoundError
from src.modules.fulfillment.domain.value_objects.order_status import OrderItemStatus
from src.modules.fulfillment.domain.value_objects.order_status import OrderStatus
from src.modules.fulfillment.domain.value_objects.source_item_demand_status import (
    SourceItemDemandStatus,
)
from src.modules.platform.domain.exceptions import InsufficientPermissionsError
from src.modules.platform.domain.value_objects.permission import Permission
from tests.factories import make_user
from tests.unit.lifecycle.fake_demand_reconciler import demand_reconciler
from tests.unit.order._helpers import FailingRecomputeSchedule
from tests.unit.order._helpers import FakeAllocationRepository
from tests.unit.order._helpers import FakeDemandRepository
from tests.unit.order._helpers import FakeEventBus
from tests.unit.order._helpers import FakeOrderItemRepository
from tests.unit.order._helpers import FakeOrderRepository
from tests.unit.order._helpers import FakeRecomputeSchedule
from tests.unit.order._helpers import FakeSourceItemAllocationRepository
from tests.unit.order._helpers import FakeSourceItemDemandRepository
from tests.unit.order._helpers import FakeUnitOfWork
from tests.unit.order._helpers import make_allocation
from tests.unit.order._helpers import make_demand
from tests.unit.order._helpers import make_order
from tests.unit.order._helpers import make_order_item
from tests.unit.order._helpers import make_source_item_allocation
from tests.unit.order._helpers import make_source_item_demand


class TestCancelOrder:
    def setup_method(self):
        self.actor = make_user(
            id=1, permissions=[Permission.WRITE_ORDERS, Permission.MANAGE_ORDERS]
        )
        self.order_repo = FakeOrderRepository()
        self.order_item_repo = FakeOrderItemRepository()
        self.allocation_repo = FakeAllocationRepository()
        self.demand_repo = FakeDemandRepository()
        self.bus = FakeEventBus()
        self.uow = FakeUnitOfWork()
        self.use_case = CancelOrder(
            order_repo=self.order_repo,
            order_item_repo=self.order_item_repo,
            allocation_repo=self.allocation_repo,
            event_bus=self.bus,
            uow=self.uow,
            reconciler=demand_reconciler(
                orders=self.order_repo,
                order_items=self.order_item_repo,
                bought_demands=self.demand_repo,
                bought_allocations=self.allocation_repo,
            ),
        )

    async def test_cancels_draft_order(self):
        order = make_order(id=1, status=OrderStatus.DRAFT)
        await self.order_repo.save(order)
        result = await self.use_case.execute(actor=self.actor, order_id=1)
        assert result.status == "canceled"

    async def test_not_found_raises(self):
        with pytest.raises(OrderNotFoundError):
            await self.use_case.execute(actor=self.actor, order_id=999)

    async def test_already_canceled_raises(self):
        order = make_order(id=1, status=OrderStatus.CANCELED)
        await self.order_repo.save(order)
        with pytest.raises(OrderCannotBeCanceledError):
            await self.use_case.execute(actor=self.actor, order_id=1)

    async def test_fully_delivered_cannot_be_canceled(self):
        order = make_order(id=1, status=OrderStatus.DELIVERED)
        await self.order_repo.save(order)
        with pytest.raises(OrderCannotBeCanceledError):
            await self.use_case.execute(actor=self.actor, order_id=1)

    async def test_requires_write_orders(self):
        order = make_order(id=1, status=OrderStatus.DRAFT)
        await self.order_repo.save(order)
        permissionless = make_user(id=2, permissions=[])
        with pytest.raises(InsufficientPermissionsError):
            await self.use_case.execute(actor=permissionless, order_id=1)
        assert (await self.order_repo.get_by_id(1)).status == "draft"

    async def test_cancelling_a_submitted_order_requires_manage_orders(self):
        """h1: cancelling past DRAFT/REQUESTED deallocates every linked
        demand, so it escalates to manage:orders."""
        order = make_order(id=1, status=OrderStatus.ORDERED)
        order_item = make_order_item(id=1, order_id=1, status=OrderItemStatus.ORDERED)
        demand = make_demand(id=1, status=BoughtItemDemandStatus.ALLOCATED)
        allocation = make_allocation(demand_item_id=1, order_item_id=1)
        await self.order_repo.save(order)
        await self.order_item_repo.save(order_item)
        allocation_repo = FakeAllocationRepository([allocation])
        use_case = CancelOrder(
            order_repo=self.order_repo,
            order_item_repo=self.order_item_repo,
            allocation_repo=allocation_repo,
            event_bus=self.bus,
            uow=self.uow,
            reconciler=demand_reconciler(
                orders=self.order_repo,
                order_items=self.order_item_repo,
                bought_demands=FakeDemandRepository([demand]),
                bought_allocations=allocation_repo,
            ),
        )
        write_only = make_user(id=2, permissions=[Permission.WRITE_ORDERS])
        with pytest.raises(InsufficientPermissionsError):
            await use_case.execute(actor=write_only, order_id=1)
        assert (await self.order_repo.get_by_id(1)).status == "ordered"
        # Nothing deallocated.
        assert await allocation_repo.get_by_order_item_id(1) == [allocation]

    async def test_creator_with_write_orders_can_cancel_a_draft(self):
        """Positive control: the escalation must not block the ordinary
        "cancel my own draft" workflow."""
        order = make_order(id=1, status=OrderStatus.DRAFT)
        await self.order_repo.save(order)
        write_only = make_user(id=2, permissions=[Permission.WRITE_ORDERS])
        result = await self.use_case.execute(actor=write_only, order_id=1)
        assert result.status == "canceled"

    async def test_cancellation_deallocates_undelivered_items(self):
        order = make_order(id=1, status=OrderStatus.ORDERED)
        order_item = make_order_item(id=1, order_id=1, status=OrderItemStatus.ORDERED)
        demand = make_demand(id=1, status=BoughtItemDemandStatus.ALLOCATED)
        allocation = make_allocation(demand_item_id=1, order_item_id=1)
        await self.order_repo.save(order)
        await self.order_item_repo.save(order_item)
        self.demand_repo = FakeDemandRepository([demand])
        self.allocation_repo = FakeAllocationRepository([allocation])
        use_case = CancelOrder(
            order_repo=self.order_repo,
            order_item_repo=self.order_item_repo,
            allocation_repo=self.allocation_repo,
            event_bus=self.bus,
            uow=self.uow,
            reconciler=demand_reconciler(
                orders=self.order_repo,
                order_items=self.order_item_repo,
                bought_demands=self.demand_repo,
                bought_allocations=self.allocation_repo,
            ),
        )
        await use_case.execute(actor=self.actor, order_id=1)
        demand_after = await self.demand_repo.get_by_id(1)
        assert demand_after.status == "open"
        assert len(self.allocation_repo.allocations) == 0
        assert (await self.order_item_repo.get_by_id(1)).status == "canceled"

    async def test_cancellation_preserves_delivered_allocations(self):
        order = make_order(id=1, status=OrderStatus.ORDERED)
        delivered_item = make_order_item(id=1, order_id=1, status=OrderItemStatus.DELIVERED)
        demand = make_demand(id=1, status=BoughtItemDemandStatus.FULFILLED)
        allocation = make_allocation(demand_item_id=1, order_item_id=1)
        await self.order_repo.save(order)
        await self.order_item_repo.save(delivered_item)
        self.demand_repo = FakeDemandRepository([demand])
        self.allocation_repo = FakeAllocationRepository([allocation])
        use_case = CancelOrder(
            order_repo=self.order_repo,
            order_item_repo=self.order_item_repo,
            allocation_repo=self.allocation_repo,
            event_bus=self.bus,
            uow=self.uow,
            reconciler=demand_reconciler(
                orders=self.order_repo,
                order_items=self.order_item_repo,
                bought_demands=self.demand_repo,
                bought_allocations=self.allocation_repo,
            ),
        )
        await use_case.execute(actor=self.actor, order_id=1)
        assert len(self.allocation_repo.allocations) == 1
        assert (await self.order_item_repo.get_by_id(1)).status == "delivered"

    async def test_publishes_event_with_creator_and_actor(self):
        order = make_order(id=1, status=OrderStatus.ORDERED, creator_id=99)
        await self.order_repo.save(order)
        await self.use_case.execute(actor=self.actor, order_id=1)
        (event,) = self.bus.published
        assert event.creator_id == 99
        assert event.actor_id == self.actor.id

    async def test_cancellation_deallocates_undelivered_source_item_demand(self):
        order = make_order(id=1, status=OrderStatus.ORDERED)
        order_item = make_order_item(id=1, order_id=1, status=OrderItemStatus.ORDERED)
        base_demand = make_source_item_demand(id=1, status=SourceItemDemandStatus.ALLOCATED)
        base_allocation = make_source_item_allocation(demand_item_id=1, order_item_id=1)
        await self.order_repo.save(order)
        await self.order_item_repo.save(order_item)
        source_item_demand_repo = FakeSourceItemDemandRepository([base_demand])
        source_item_allocation_repo = FakeSourceItemAllocationRepository([base_allocation])
        use_case = CancelOrder(
            order_repo=self.order_repo,
            order_item_repo=self.order_item_repo,
            allocation_repo=self.allocation_repo,
            event_bus=self.bus,
            uow=self.uow,
            source_item_allocation_repo=source_item_allocation_repo,
            reconciler=demand_reconciler(
                orders=self.order_repo,
                order_items=self.order_item_repo,
                bought_demands=self.demand_repo,
                bought_allocations=self.allocation_repo,
                source_demands=source_item_demand_repo,
                source_allocations=source_item_allocation_repo,
            ),
        )
        await use_case.execute(actor=self.actor, order_id=1)
        assert (await source_item_demand_repo.get_by_id(1)).status == "open"
        assert len(source_item_allocation_repo.allocations) == 0
        assert (await self.order_item_repo.get_by_id(1)).status == "canceled"

    async def test_recompute_is_called_exactly_once_on_success(self):
        order = make_order(id=1, status=OrderStatus.DRAFT)
        await self.order_repo.save(order)
        recompute = FakeRecomputeSchedule()
        use_case = CancelOrder(
            order_repo=self.order_repo,
            order_item_repo=self.order_item_repo,
            allocation_repo=self.allocation_repo,
            recompute_schedule=recompute,
            event_bus=self.bus,
            uow=self.uow,
            reconciler=demand_reconciler(
                orders=self.order_repo,
                order_items=self.order_item_repo,
                bought_demands=self.demand_repo,
                bought_allocations=self.allocation_repo,
            ),
        )
        await use_case.execute(actor=self.actor, order_id=1)
        assert recompute.execute_all_calls == 1

    async def test_recompute_failure_does_not_roll_back_the_commit(self):
        order = make_order(id=1, status=OrderStatus.ORDERED)
        order_item = make_order_item(id=1, order_id=1, status=OrderItemStatus.ORDERED)
        base_demand = make_source_item_demand(id=1, status=SourceItemDemandStatus.ALLOCATED)
        base_allocation = make_source_item_allocation(demand_item_id=1, order_item_id=1)
        await self.order_repo.save(order)
        await self.order_item_repo.save(order_item)
        source_item_demand_repo = FakeSourceItemDemandRepository([base_demand])
        source_item_allocation_repo = FakeSourceItemAllocationRepository([base_allocation])
        recompute = FailingRecomputeSchedule()
        use_case = CancelOrder(
            order_repo=self.order_repo,
            order_item_repo=self.order_item_repo,
            allocation_repo=self.allocation_repo,
            recompute_schedule=recompute,
            event_bus=self.bus,
            uow=self.uow,
            source_item_allocation_repo=source_item_allocation_repo,
            reconciler=demand_reconciler(
                orders=self.order_repo,
                order_items=self.order_item_repo,
                bought_demands=self.demand_repo,
                bought_allocations=self.allocation_repo,
                source_demands=source_item_demand_repo,
                source_allocations=source_item_allocation_repo,
            ),
        )
        result = await use_case.execute(actor=self.actor, order_id=1)
        assert recompute.attempts == 1
        assert self.uow.committed is True
        assert result.status == "canceled"
        assert await source_item_allocation_repo.get_by_order_item_id(1) == []
