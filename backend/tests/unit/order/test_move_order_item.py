"""
Unit tests for MoveOrderItem: moving a line to another order of the same
kind, what it takes over from the target and what it keeps, and the moves
it refuses. No database, no HTTP; every dependency is an in-memory fake.
"""

import pytest

from src.modules.fulfillment.application.use_cases.order.move_order_item import MoveOrderItem
from src.modules.fulfillment.domain.errors import OrderItemCannotBeMovedError
from src.modules.fulfillment.domain.errors import OrderItemNotFoundError
from src.modules.fulfillment.domain.errors import OrderNotFoundError
from src.modules.fulfillment.domain.value_objects.order_status import OrderItemStatus
from src.modules.fulfillment.domain.value_objects.order_status import OrderStatus
from src.modules.platform.domain.exceptions import InsufficientPermissionsError
from src.modules.platform.domain.value_objects.permission import Permission
from tests.factories import make_user
from tests.unit.lifecycle.fake_reconciler import give_order_facts
from tests.unit.lifecycle.fake_reconciler import give_order_item_facts
from tests.unit.lifecycle.fake_reconciler import order_reconciler
from tests.unit.order._helpers import FakeAllocationRepository
from tests.unit.order._helpers import FakeOrderItemRepository
from tests.unit.order._helpers import FakeOrderRepository
from tests.unit.order._helpers import FakeUnitOfWork
from tests.unit.order._helpers import make_allocation
from tests.unit.order._helpers import make_order
from tests.unit.order._helpers import make_order_item


class TestMoveOrderItem:
    def setup_method(self):
        self.actor = make_user(permissions=[Permission.WRITE_ORDERS])
        self.source = make_order(id=1, status=OrderStatus.DRAFT, supplier_id=1)
        self.target = make_order(id=2, status=OrderStatus.DRAFT, supplier_id=2)
        self.order_repo = FakeOrderRepository([self.source, self.target])
        self.uow = FakeUnitOfWork()
        order_item_repo = FakeOrderItemRepository()
        self.use_case = MoveOrderItem(
            order_repo=self.order_repo,
            order_item_repo=order_item_repo,
            uow=self.uow,
            reconciler=order_reconciler(self.order_repo, order_item_repo),
        )

    def _use_case(self, order_item_repo: FakeOrderItemRepository) -> MoveOrderItem:
        return MoveOrderItem(
            order_repo=self.order_repo,
            order_item_repo=order_item_repo,
            uow=self.uow,
            reconciler=order_reconciler(self.order_repo, order_item_repo),
        )

    async def test_reparents_item_and_adopts_target_supplier(self):
        item = make_order_item(id=1, order_id=1, status=OrderItemStatus.PENDING)
        order_item_repo = FakeOrderItemRepository([item])
        use_case = self._use_case(order_item_repo)

        result = await use_case.execute(
            actor=self.actor, source_order_id=1, order_item_id=1, target_order_id=2
        )

        assert result.order_id == 2
        assert (await order_item_repo.get_by_id(1)).order_id == 2
        assert (await order_item_repo.get_by_id(1)).supplier_id == 2
        assert self.uow.committed is True

    async def test_assigns_next_position_on_target_order(self):
        existing_target_item = make_order_item(id=2, order_id=2, status=OrderItemStatus.PENDING)
        item = make_order_item(id=1, order_id=1, status=OrderItemStatus.PENDING)
        order_item_repo = FakeOrderItemRepository([item, existing_target_item])
        use_case = self._use_case(order_item_repo)

        await use_case.execute(
            actor=self.actor, source_order_id=1, order_item_id=1, target_order_id=2
        )

        assert (await order_item_repo.get_by_id(1)).position == 2

    async def test_status_and_lot_position_untouched(self):
        # A line with deliveries stays on its order, so an ordered one moves.
        item = give_order_item_facts(
            make_order_item(id=1, order_id=1, status=OrderItemStatus.ORDERED)
        )
        item.lot_position_id = 42
        order_item_repo = FakeOrderItemRepository([item])
        use_case = self._use_case(order_item_repo)

        await use_case.execute(
            actor=self.actor, source_order_id=1, order_item_id=1, target_order_id=2
        )

        moved = await order_item_repo.get_by_id(1)
        assert moved.status == "ordered"
        assert moved.lot_position_id == 42

    async def test_allocations_are_not_deleted(self):
        item = make_order_item(id=1, order_id=1, status=OrderItemStatus.PENDING)
        order_item_repo = FakeOrderItemRepository([item])
        allocation_repo = FakeAllocationRepository([make_allocation(order_item_id=1)])
        use_case = self._use_case(order_item_repo)

        await use_case.execute(
            actor=self.actor, source_order_id=1, order_item_id=1, target_order_id=2
        )

        assert len(await allocation_repo.get_by_order_item_id(1)) == 1

    async def test_moving_to_same_order_raises(self):
        item = make_order_item(id=1, order_id=1, status=OrderItemStatus.PENDING)
        order_item_repo = FakeOrderItemRepository([item])
        use_case = self._use_case(order_item_repo)

        with pytest.raises(OrderItemCannotBeMovedError):
            await use_case.execute(
                actor=self.actor, source_order_id=1, order_item_id=1, target_order_id=1
            )

    async def test_moving_to_canceled_order_raises(self):
        # Canceled by someone, so the order carries its cancel intent.
        canceled_target = give_order_facts(
            make_order(id=3, status=OrderStatus.CANCELED, supplier_id=1)
        )
        order_repo = FakeOrderRepository([self.source, canceled_target])
        item = make_order_item(id=1, order_id=1, status=OrderItemStatus.PENDING)
        order_item_repo = FakeOrderItemRepository([item])
        use_case = MoveOrderItem(
            order_repo=order_repo,
            order_item_repo=order_item_repo,
            uow=self.uow,
            reconciler=order_reconciler(order_repo, order_item_repo),
        )

        with pytest.raises(OrderItemCannotBeMovedError):
            await use_case.execute(
                actor=self.actor, source_order_id=1, order_item_id=1, target_order_id=3
            )

    async def test_unprivileged_actor_cannot_move(self):
        actor = make_user(permissions=[])
        item = make_order_item(id=1, order_id=1, status=OrderItemStatus.PENDING)
        order_item_repo = FakeOrderItemRepository([item])
        use_case = self._use_case(order_item_repo)

        with pytest.raises(InsufficientPermissionsError):
            await use_case.execute(
                actor=actor, source_order_id=1, order_item_id=1, target_order_id=2
            )

    async def test_source_order_not_found_raises(self):
        item = make_order_item(id=1, order_id=99, status=OrderItemStatus.PENDING)
        order_item_repo = FakeOrderItemRepository([item])
        use_case = self._use_case(order_item_repo)

        with pytest.raises(OrderNotFoundError):
            await use_case.execute(
                actor=self.actor, source_order_id=99, order_item_id=1, target_order_id=2
            )

    async def test_target_order_not_found_raises(self):
        item = make_order_item(id=1, order_id=1, status=OrderItemStatus.PENDING)
        order_item_repo = FakeOrderItemRepository([item])
        use_case = self._use_case(order_item_repo)

        with pytest.raises(OrderNotFoundError):
            await use_case.execute(
                actor=self.actor, source_order_id=1, order_item_id=1, target_order_id=99
            )

    async def test_item_not_found_in_source_raises(self):
        item = make_order_item(id=1, order_id=2, status=OrderItemStatus.PENDING)
        order_item_repo = FakeOrderItemRepository([item])
        use_case = self._use_case(order_item_repo)

        with pytest.raises(OrderItemNotFoundError):
            await use_case.execute(
                actor=self.actor, source_order_id=1, order_item_id=1, target_order_id=2
            )
