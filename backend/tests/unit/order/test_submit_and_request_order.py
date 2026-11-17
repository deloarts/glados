"""
Unit tests for SubmitOrder and RequestOrder, the two transitions that move
an order out of draft, with the states each one refuses and the permission
both require. No database, no HTTP; every dependency is an in-memory fake.
"""

from datetime import UTC
from datetime import datetime

import pytest

from src.modules.fulfillment.application.use_cases.order.update_order import RequestOrder
from src.modules.fulfillment.application.use_cases.order.update_order import SubmitOrder
from src.modules.fulfillment.domain.errors import OrderAlreadyRequestedError
from src.modules.fulfillment.domain.errors import OrderAlreadySubmittedError
from src.modules.fulfillment.domain.errors import OrderNotFoundError
from src.modules.fulfillment.domain.value_objects.order_status import OrderStatus
from src.modules.platform.domain.exceptions import InsufficientPermissionsError
from src.modules.platform.domain.value_objects.permission import Permission
from tests.factories import make_user
from tests.unit.lifecycle.fake_reconciler import order_reconciler
from tests.unit.order._helpers import FakeEventBus
from tests.unit.order._helpers import FakeOrderItemRepository
from tests.unit.order._helpers import FakeOrderRepository
from tests.unit.order._helpers import FakeUnitOfWork
from tests.unit.order._helpers import make_order


class TestSubmitOrder:
    def setup_method(self):
        self.actor = make_user(permissions=[Permission.WRITE_ORDERS])
        self.order_repo = FakeOrderRepository()
        self.bus = FakeEventBus()
        self.order_item_repo = FakeOrderItemRepository()
        self.use_case = SubmitOrder(
            self.order_repo,
            event_bus=self.bus,
            uow=FakeUnitOfWork(),
            reconciler=order_reconciler(self.order_repo, self.order_item_repo),
            order_item_repo=self.order_item_repo,
        )

    async def test_draft_transitions_to_ordered(self):
        order = make_order(id=1, status=OrderStatus.DRAFT)
        await self.order_repo.save(order)
        result = await self.use_case.execute(actor=self.actor, order_id=1)
        assert result.status == "ordered"
        # Full UTC instant, not just the day, durations like "ordered → delivered"
        # are only answerable if the time of day survives.
        assert result.ordered_date.tzinfo is not None
        assert result.ordered_date.date() == datetime.now(UTC).date()
        assert len(self.bus.published) == 1

    async def test_requested_can_be_submitted(self):
        order = make_order(id=1, status=OrderStatus.REQUESTED)
        await self.order_repo.save(order)
        result = await self.use_case.execute(actor=self.actor, order_id=1)
        assert result.status == "ordered"

    async def test_already_ordered_raises(self):
        order = make_order(id=1, status=OrderStatus.ORDERED)
        await self.order_repo.save(order)
        with pytest.raises(OrderAlreadySubmittedError):
            await self.use_case.execute(actor=self.actor, order_id=1)

    async def test_not_found_raises(self):
        with pytest.raises(OrderNotFoundError):
            await self.use_case.execute(actor=self.actor, order_id=999)

    async def test_requires_write_orders(self):
        order = make_order(id=1, status=OrderStatus.DRAFT)
        await self.order_repo.save(order)
        permissionless = make_user(permissions=[])
        with pytest.raises(InsufficientPermissionsError):
            await self.use_case.execute(actor=permissionless, order_id=1)
        assert (await self.order_repo.get_by_id(1)).status == "draft"


class TestRequestOrder:
    def setup_method(self):
        self.actor = make_user(permissions=[Permission.WRITE_ORDERS])
        self.order_repo = FakeOrderRepository()
        self.bus = FakeEventBus()
        self.order_item_repo = FakeOrderItemRepository()
        self.use_case = RequestOrder(
            self.order_repo,
            event_bus=self.bus,
            uow=FakeUnitOfWork(),
            reconciler=order_reconciler(self.order_repo, self.order_item_repo),
            order_item_repo=self.order_item_repo,
        )

    async def test_draft_transitions_to_requested(self):
        order = make_order(id=1, status=OrderStatus.DRAFT)
        await self.order_repo.save(order)
        result = await self.use_case.execute(actor=self.actor, order_id=1)
        assert result.status == "requested"

    async def test_already_requested_raises(self):
        order = make_order(id=1, status=OrderStatus.REQUESTED)
        await self.order_repo.save(order)
        with pytest.raises(OrderAlreadyRequestedError):
            await self.use_case.execute(actor=self.actor, order_id=1)

    async def test_already_ordered_raises(self):
        order = make_order(id=1, status=OrderStatus.ORDERED)
        await self.order_repo.save(order)
        with pytest.raises(OrderAlreadyRequestedError):
            await self.use_case.execute(actor=self.actor, order_id=1)

    async def test_not_found_raises(self):
        with pytest.raises(OrderNotFoundError):
            await self.use_case.execute(actor=self.actor, order_id=999)

    async def test_requires_write_orders(self):
        order = make_order(id=1, status=OrderStatus.DRAFT)
        await self.order_repo.save(order)
        permissionless = make_user(permissions=[])
        with pytest.raises(InsufficientPermissionsError):
            await self.use_case.execute(actor=permissionless, order_id=1)
        assert (await self.order_repo.get_by_id(1)).status == "draft"
