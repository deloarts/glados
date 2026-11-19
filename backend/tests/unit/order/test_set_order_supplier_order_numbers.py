"""
Unit tests for the supplier order numbers of an order: how a list is
normalised, the rule that keeps them editable with write:orders in every
status until the order is delivered or canceled, and SetOrderSupplierOrderNumbers
with its changelog entry and edit version. No database, no HTTP; every
dependency is an in-memory fake.
"""

from datetime import UTC
from datetime import datetime

import pytest

from src.modules.fulfillment.application.dto.order_dto import SetOrderSupplierOrderNumbersCommand
from src.modules.fulfillment.application.use_cases.order.set_order_supplier_order_numbers import (
    SetOrderSupplierOrderNumbers,
)
from src.modules.fulfillment.domain.errors import OrderNotFoundError
from src.modules.fulfillment.domain.errors import OrderSupplierOrderNumbersLockedError
from src.modules.fulfillment.domain.services.lifecycle.intents import ORDER_INTENTS
from src.modules.fulfillment.domain.services.supplier_order_numbers import (
    normalized_supplier_order_numbers,
)
from src.modules.fulfillment.domain.value_objects.order_status import OrderStatus
from src.modules.platform.domain.exceptions import ConcurrentModificationError
from src.modules.platform.domain.exceptions import InsufficientPermissionsError
from src.modules.platform.domain.value_objects.permission import Permission
from src.shared_kernel.domain.value_objects.lifecycle_action import LifecycleAction
from tests.factories import make_user
from tests.unit.order._helpers import FakeOrderItemRepository
from tests.unit.order._helpers import FakeOrderRepository
from tests.unit.order._helpers import FakeUnitOfWork
from tests.unit.order._helpers import make_order

_ACTION = LifecycleAction.EDIT_SUPPLIER_ORDER_NUMBERS
_OPEN = (
    OrderStatus.DRAFT,
    OrderStatus.REQUESTED,
    OrderStatus.PARTIALLY_ORDERED,
    OrderStatus.ORDERED,
    OrderStatus.PARTIALLY_DELIVERED,
)
_TERMINAL = (OrderStatus.DELIVERED, OrderStatus.CANCELED)


class TestNormalizedSupplierOrderNumbers:
    def test_trims_and_drops_blank_entries(self):
        assert normalized_supplier_order_numbers(["  AB-1 ", "", "   ", "AB-2"]) == [
            "AB-1",
            "AB-2",
        ]

    def test_keeps_the_first_spelling_of_a_number_entered_twice(self):
        assert normalized_supplier_order_numbers(["ab-1", "AB-2", "AB-1 "]) == ["ab-1", "AB-2"]

    def test_keeps_the_order_of_entry(self):
        assert normalized_supplier_order_numbers(["Z-9", "A-1", "Müller-7"]) == [
            "Z-9",
            "A-1",
            "Müller-7",
        ]

    def test_an_empty_list_stays_empty(self):
        assert normalized_supplier_order_numbers([]) == []


class TestIntentRule:
    @pytest.mark.parametrize("status", _OPEN)
    def test_a_user_with_only_write_orders_is_offered_it_until_the_order_ends(self, status):
        writer = make_user(permissions=[Permission.WRITE_ORDERS])
        order = make_order(status=status)

        assert _ACTION in ORDER_INTENTS.allowed_actions(order, None, writer)

    @pytest.mark.parametrize("status", _TERMINAL)
    def test_a_delivered_or_canceled_order_does_not_offer_it(self, status):
        manager = make_user(permissions=[Permission.WRITE_ORDERS, Permission.MANAGE_ORDERS])
        order = make_order(status=status)

        assert _ACTION not in ORDER_INTENTS.allowed_actions(order, None, manager)

    def test_an_order_someone_canceled_does_not_offer_it_whatever_it_derives(self):
        manager = make_user(permissions=[Permission.WRITE_ORDERS, Permission.MANAGE_ORDERS])
        order = make_order(status=OrderStatus.PARTIALLY_DELIVERED)
        order.canceled_at = datetime(2026, 11, 1, tzinfo=UTC)

        assert _ACTION not in ORDER_INTENTS.allowed_actions(order, None, manager)


class TestSetOrderSupplierOrderNumbers:
    def setup_method(self):
        self.actor = make_user(permissions=[Permission.WRITE_ORDERS])
        self.order = make_order(id=1, status=OrderStatus.ORDERED)
        self.order_repo = FakeOrderRepository([self.order])
        self.uow = FakeUnitOfWork()
        self.use_case = SetOrderSupplierOrderNumbers(
            self.order_repo, FakeOrderItemRepository(), uow=self.uow
        )

    async def _set(self, numbers: list[str], **kwargs) -> object:
        cmd = SetOrderSupplierOrderNumbersCommand(numbers=numbers, **kwargs)
        return await self.use_case.execute(actor=self.actor, order_id=1, cmd=cmd)

    async def test_an_ordered_order_takes_numbers_from_a_user_without_manage_orders(self):
        result = await self._set([" AB-24117", "AB-24131", "ab-24117"])

        assert result.supplier_order_numbers == ["AB-24117", "AB-24131"]
        assert self.order.supplier_order_numbers == ["AB-24117", "AB-24131"]
        assert self.uow.committed

    async def test_a_change_moves_the_edit_version_and_is_logged_as_a_list(self):
        self.order.supplier_order_numbers = ["AB-1"]

        await self._set(["AB-1", "AB-2"])

        assert self.order.edit_version == 1
        entry = self.order.changes[-1]
        assert entry.field == "supplier_order_numbers"
        assert entry.old == "AB-1"
        assert entry.new == "AB-1, AB-2"

    async def test_clearing_the_list_is_logged_as_empty(self):
        self.order.supplier_order_numbers = ["AB-1"]

        await self._set([])

        assert self.order.supplier_order_numbers == []
        assert self.order.changes[-1].new == "empty"

    async def test_the_same_list_again_changes_nothing(self):
        self.order.supplier_order_numbers = ["AB-1"]

        await self._set([" AB-1 "])

        assert self.order.edit_version == 0
        assert self.order.changes == []

    @pytest.mark.parametrize("status", _TERMINAL)
    async def test_a_delivered_or_canceled_order_refuses_the_change(self, status):
        self.order.status = status

        with pytest.raises(OrderSupplierOrderNumbersLockedError):
            await self._set(["AB-1"])
        assert self.order.supplier_order_numbers == []

    async def test_an_order_someone_canceled_refuses_the_change(self):
        self.order.status = OrderStatus.PARTIALLY_DELIVERED
        self.order.canceled_at = datetime(2026, 11, 1, tzinfo=UTC)

        with pytest.raises(OrderSupplierOrderNumbersLockedError):
            await self._set(["AB-1"])

    async def test_a_user_without_write_orders_is_refused(self):
        self.actor = make_user(permissions=[])

        with pytest.raises(InsufficientPermissionsError):
            await self._set(["AB-1"])

    async def test_an_older_edit_version_is_refused(self):
        self.order.edit_version = 3

        with pytest.raises(ConcurrentModificationError):
            await self._set(["AB-1"], expected_edit_version=2)

    async def test_an_unknown_order_is_not_found(self):
        cmd = SetOrderSupplierOrderNumbersCommand(numbers=["AB-1"])

        with pytest.raises(OrderNotFoundError):
            await self.use_case.execute(actor=self.actor, order_id=99, cmd=cmd)
