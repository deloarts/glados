"""
Unit tests for CreateOrder: the new order, its creation event and the
permission it requires. No database, no HTTP; every dependency is an
in-memory fake.
"""

import pytest

from src.modules.fulfillment.application.dto.order_dto import CreateOrderCommand
from src.modules.fulfillment.application.use_cases.order.create_order import CreateOrder
from src.modules.platform.domain.exceptions import InsufficientPermissionsError
from src.modules.platform.domain.value_objects.permission import Permission
from tests.factories import make_user
from tests.unit.order._helpers import FakeAdminSettingsRepository
from tests.unit.order._helpers import FakeEventBus
from tests.unit.order._helpers import FakeOrderRepository
from tests.unit.order._helpers import FakeUnitOfWork


class TestCreateOrder:
    def setup_method(self):
        self.actor = make_user(permissions=[Permission.WRITE_ORDERS])
        self.order_repo = FakeOrderRepository()
        self.bus = FakeEventBus()
        self.admin_settings_repo = FakeAdminSettingsRepository()
        self.use_case = CreateOrder(
            self.order_repo,
            event_bus=self.bus,
            admin_settings_repo=self.admin_settings_repo,
            uow=FakeUnitOfWork(),
        )

    async def test_creates_order_successfully(self):
        result = await self.use_case.execute(
            actor=self.actor, cmd=CreateOrderCommand(supplier_id=1)
        )
        assert result.id > 0
        assert result.status == "draft"
        assert result.order_number.startswith("ORD-")

    async def test_event_has_correct_fields(self):
        result = await self.use_case.execute(
            actor=self.actor, cmd=CreateOrderCommand(supplier_id=1)
        )
        (event,) = self.bus.published
        assert event.order_id == result.id
        assert event.creator_id == self.actor.id
        assert event.supplier_id == 1

    async def test_unprivileged_cannot_create(self):
        actor = make_user(permissions=[])
        with pytest.raises(InsufficientPermissionsError):
            await self.use_case.execute(actor=actor, cmd=CreateOrderCommand(supplier_id=1))
