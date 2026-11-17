"""
Unit tests for UpdateOrder: partial updates that leave other fields alone,
the supplier change, the manage permission a submitted order needs, and
the schedule recompute after a delivery date change. No database, no HTTP;
every dependency is an in-memory fake.
"""

from datetime import UTC
from datetime import date
from datetime import datetime

import pytest

from src.modules.catalogue.domain.errors import SupplierNotFoundError
from src.modules.fulfillment.application.dto.order_dto import UpdateOrderCommand
from src.modules.fulfillment.application.use_cases.order.update_order import UpdateOrder
from src.modules.fulfillment.domain.errors import OrderAlreadySubmittedError
from src.modules.fulfillment.domain.errors import OrderCanceledError
from src.modules.fulfillment.domain.errors import OrderNotFoundError
from src.modules.fulfillment.domain.value_objects.order_status import OrderItemStatus
from src.modules.fulfillment.domain.value_objects.order_status import OrderStatus
from src.modules.platform.domain.value_objects.permission import Permission
from tests.factories import make_user
from tests.unit.order._helpers import FailingRecomputeSchedule
from tests.unit.order._helpers import FakeOrderItemRepository
from tests.unit.order._helpers import FakeOrderRepository
from tests.unit.order._helpers import FakeRecomputeSchedule
from tests.unit.order._helpers import FakeSupplierRepository
from tests.unit.order._helpers import FakeUnitOfWork
from tests.unit.order._helpers import make_order
from tests.unit.order._helpers import make_order_item
from tests.unit.order._helpers import make_supplier


class TestUpdateOrder:
    def setup_method(self):
        self.actor = make_user(permissions=[Permission.WRITE_ORDERS])
        self.order = make_order(id=1, status=OrderStatus.DRAFT)
        self.supplier = make_supplier(id=2, name="New Supplier")
        self.order_repo = FakeOrderRepository([self.order])
        self.order_item_repo = FakeOrderItemRepository()
        self.supplier_repo = FakeSupplierRepository([make_supplier(id=1), self.supplier])
        self.uow = FakeUnitOfWork()
        self.use_case = UpdateOrder(
            self.order_repo, self.order_item_repo, self.supplier_repo, uow=self.uow
        )

    def _cmd(self, **kwargs) -> UpdateOrderCommand:
        defaults = dict()
        defaults.update(kwargs)
        return UpdateOrderCommand(**defaults)

    async def test_updates_note(self):
        result = await self.use_case.execute(
            actor=self.actor, order_id=1, cmd=self._cmd(note="Urgent")
        )
        assert result.note == "Urgent"

    async def test_the_changelog_names_each_changed_field_with_its_old_and_new_value(self):
        self.order.note = "Old"

        await self.use_case.execute(actor=self.actor, order_id=1, cmd=self._cmd(note="Urgent"))

        [entry] = [c for c in (await self.order_repo.get_by_id(1)).changes if "note" in c]
        assert entry.endswith("note: Old → Urgent")
        assert (entry.field, entry.old, entry.new) == ("note", "Old", "Urgent")

    async def test_not_found_raises(self):
        with pytest.raises(OrderNotFoundError):
            await self.use_case.execute(actor=self.actor, order_id=999, cmd=self._cmd())

    async def test_already_submitted_cannot_be_updated_without_manage(self):
        ordered = make_order(id=2, status=OrderStatus.ORDERED)
        await self.order_repo.save(ordered)
        with pytest.raises(OrderAlreadySubmittedError):
            await self.use_case.execute(actor=self.actor, order_id=2, cmd=self._cmd())

    async def test_an_order_someone_canceled_keeps_its_header(self):
        manager = make_user(permissions=[Permission.WRITE_ORDERS, Permission.MANAGE_ORDERS])
        canceled = make_order(id=2, status=OrderStatus.CANCELED)
        canceled.canceled_at = datetime(2026, 11, 1, tzinfo=UTC)
        await self.order_repo.save(canceled)

        with pytest.raises(OrderCanceledError):
            await self.use_case.execute(actor=manager, order_id=2, cmd=self._cmd(note="Late"))
        assert self.uow.committed is False

    async def test_manager_can_update_submitted_order(self):
        manager = make_user(permissions=[Permission.WRITE_ORDERS, Permission.MANAGE_ORDERS])
        ordered = make_order(id=2, status=OrderStatus.ORDERED)
        await self.order_repo.save(ordered)
        result = await self.use_case.execute(
            actor=manager, order_id=2, cmd=self._cmd(note="Managed")
        )
        assert result.note == "Managed"

    async def test_changing_supplier_to_nonexistent_raises(self):
        with pytest.raises(SupplierNotFoundError):
            await self.use_case.execute(
                actor=self.actor, order_id=1, cmd=self._cmd(supplier_id=999)
            )

    async def test_changing_supplier_updates_supplier_id(self):
        result = await self.use_case.execute(
            actor=self.actor, order_id=1, cmd=self._cmd(supplier_id=2)
        )
        assert result.supplier_id == 2

    async def test_updating_note_does_not_clear_other_fields(self):
        self.order.storage_place = "Shelf A1"
        self.order.expected_delivery_date = date(2026, 2, 1)
        result = await self.use_case.execute(
            actor=self.actor, order_id=1, cmd=self._cmd(note="Urgent")
        )
        assert result.note == "Urgent"
        assert result.storage_place == "Shelf A1"
        assert result.expected_delivery_date == date(2026, 2, 1)

    async def test_updating_storage_place_does_not_clear_note(self):
        self.order.note = "Existing note"
        result = await self.use_case.execute(
            actor=self.actor, order_id=1, cmd=self._cmd(storage_place="Shelf B2")
        )
        assert result.storage_place == "Shelf B2"
        assert result.note == "Existing note"

    async def test_recompute_is_called_once_when_items_delivery_date_updated(self):
        item = make_order_item(id=1, order_id=1, status=OrderItemStatus.PENDING)
        await self.order_item_repo.save(item)
        recompute = FakeRecomputeSchedule()
        use_case = UpdateOrder(
            self.order_repo,
            self.order_item_repo,
            self.supplier_repo,
            recompute,
            uow=self.uow,
        )
        await use_case.execute(
            actor=self.actor,
            order_id=1,
            cmd=self._cmd(update_items_delivery_date=True, expected_delivery_date=date(2026, 3, 1)),
        )
        assert recompute.execute_all_calls == 1
        assert (await self.order_item_repo.get_by_id(1)).expected_delivery_date == date(2026, 3, 1)

    async def test_recompute_not_called_when_items_delivery_date_not_updated(self):
        recompute = FakeRecomputeSchedule()
        use_case = UpdateOrder(
            self.order_repo,
            self.order_item_repo,
            self.supplier_repo,
            recompute,
            uow=self.uow,
        )
        await use_case.execute(actor=self.actor, order_id=1, cmd=self._cmd(note="Urgent"))
        assert recompute.execute_all_calls == 0

    async def test_recompute_failure_does_not_roll_back_the_commit(self):
        item = make_order_item(id=1, order_id=1, status=OrderItemStatus.PENDING)
        await self.order_item_repo.save(item)
        recompute = FailingRecomputeSchedule()
        use_case = UpdateOrder(
            self.order_repo,
            self.order_item_repo,
            self.supplier_repo,
            recompute,
            uow=self.uow,
        )
        result = await use_case.execute(
            actor=self.actor,
            order_id=1,
            cmd=self._cmd(update_items_delivery_date=True, expected_delivery_date=date(2026, 3, 1)),
        )
        assert recompute.attempts == 1
        assert self.uow.committed is True
        assert result.expected_delivery_date == date(2026, 3, 1)
