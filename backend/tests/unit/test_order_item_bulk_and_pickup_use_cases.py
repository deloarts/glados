"""
Unit tests for MarkAllOrderItemsRequested and MarkOrderItemReadyForPickup:
neither class had any dedicated test coverage. Their siblings in the same
module, MarkOrderItemOrdered, MarkAllOrderItemsOrdered, and
MarkOrderItemRequested, already have coverage in
tests/unit/order/test_mark_order_item_ordered.py; these two were the gap.

Fakes/helpers are imported from tests/unit/order/_helpers.py rather than redefined.
"""

from datetime import UTC
from datetime import datetime
from datetime import timedelta

import pytest

from src.modules.fulfillment.application.use_cases.order.mark_order_item_ordered import (
    MarkAllOrderItemsRequested,
)
from src.modules.fulfillment.application.use_cases.order.mark_order_item_ready_for_pickup import (
    MarkOrderItemReadyForPickup,
)
from src.modules.fulfillment.domain.errors import OrderItemNotFoundError
from src.modules.fulfillment.domain.errors import OrderItemNotReadyForPickupError
from src.modules.fulfillment.domain.errors import OrderNotFoundError
from src.modules.fulfillment.domain.errors import PickupInFutureError
from src.modules.fulfillment.domain.value_objects.order_status import OrderItemStatus
from src.modules.fulfillment.domain.value_objects.order_status import OrderStatus
from src.modules.platform.domain.exceptions import InsufficientPermissionsError
from tests.factories import make_user
from tests.unit.lifecycle.fake_reconciler import order_reconciler
from tests.unit.order._helpers import FakeOrderItemRepository
from tests.unit.order._helpers import FakeOrderRepository
from tests.unit.order._helpers import FakeUnitOfWork
from tests.unit.order._helpers import make_order
from tests.unit.order._helpers import make_order_item

# ── MarkAllOrderItemsRequested ──────────────────────────────────────────


class TestMarkAllOrderItemsRequested:
    async def test_order_not_found(self):
        orders, items = FakeOrderRepository(), FakeOrderItemRepository()
        use_case = MarkAllOrderItemsRequested(
            items, orders, uow=FakeUnitOfWork(), reconciler=order_reconciler(orders, items)
        )

        with pytest.raises(OrderNotFoundError):
            await use_case.execute(actor=make_user(), order_id=999)

    async def test_requires_write_orders(self):
        order = make_order(id=1)
        orders = FakeOrderRepository([order])
        items = FakeOrderItemRepository([make_order_item(id=1, order_id=1)])
        use_case = MarkAllOrderItemsRequested(
            items, orders, uow=FakeUnitOfWork(), reconciler=order_reconciler(orders, items)
        )

        with pytest.raises(InsufficientPermissionsError):
            await use_case.execute(actor=make_user(permissions=[]), order_id=1)

    async def test_only_pending_items_are_marked_requested(self):
        order = make_order(id=1, status=OrderStatus.DRAFT)
        orders = FakeOrderRepository([order])
        pending = make_order_item(id=1, order_id=1, status=OrderItemStatus.PENDING)
        already_ordered = make_order_item(id=2, order_id=1, status=OrderItemStatus.ORDERED)
        other_orders_item = make_order_item(id=3, order_id=2, status=OrderItemStatus.PENDING)
        items = FakeOrderItemRepository([pending, already_ordered, other_orders_item])
        use_case = MarkAllOrderItemsRequested(
            items, orders, uow=FakeUnitOfWork(), reconciler=order_reconciler(orders, items)
        )

        results = await use_case.execute(actor=make_user(permissions=["write:orders"]), order_id=1)

        assert [r.id for r in results] == [1]
        assert (await items.get_by_id(1)).status == OrderItemStatus.REQUESTED.value
        # The mark's own note, then the status line of the reconciler.
        changes = (await items.get_by_id(1)).changes
        assert changes[-2].endswith("Marked as requested (bulk action).")
        assert "Status: pending → requested" in changes[-1]
        # Unaffected: already past PENDING, and belongs to a different order.
        assert (await items.get_by_id(2)).status == "ordered"
        assert (await items.get_by_id(3)).status == "pending"

    async def test_auto_progresses_the_order_when_every_item_is_now_requested(self):
        order = make_order(id=1, status=OrderStatus.DRAFT)
        orders = FakeOrderRepository([order])
        items = FakeOrderItemRepository(
            [make_order_item(id=1, order_id=1, status=OrderItemStatus.PENDING)]
        )
        use_case = MarkAllOrderItemsRequested(
            items, orders, uow=FakeUnitOfWork(), reconciler=order_reconciler(orders, items)
        )

        await use_case.execute(actor=make_user(permissions=["write:orders"]), order_id=1)

        assert (await orders.get_by_id(1)).status == "requested"

    async def test_no_pending_items_marks_nothing(self):
        order = make_order(id=1, status=OrderStatus.DRAFT)
        orders = FakeOrderRepository([order])
        items = FakeOrderItemRepository(
            [make_order_item(id=1, order_id=1, status=OrderItemStatus.ORDERED)]
        )
        use_case = MarkAllOrderItemsRequested(
            items, orders, uow=FakeUnitOfWork(), reconciler=order_reconciler(orders, items)
        )

        results = await use_case.execute(actor=make_user(permissions=["write:orders"]), order_id=1)

        assert results == []


# ── MarkOrderItemReadyForPickup ──────────────────────────────────────────


class TestMarkOrderItemReadyForPickup:
    async def test_order_not_found(self):
        use_case = MarkOrderItemReadyForPickup(
            FakeOrderItemRepository(), FakeOrderRepository(), uow=FakeUnitOfWork()
        )

        with pytest.raises(OrderNotFoundError):
            await use_case.execute(actor=make_user(), order_id=999, order_item_id=1)

    async def test_requires_write_orders(self):
        order = make_order(id=1)
        orders = FakeOrderRepository([order])
        items = FakeOrderItemRepository(
            [make_order_item(id=1, order_id=1, status=OrderItemStatus.ORDERED)]
        )
        use_case = MarkOrderItemReadyForPickup(items, orders, uow=FakeUnitOfWork())

        with pytest.raises(InsufficientPermissionsError):
            await use_case.execute(actor=make_user(permissions=[]), order_id=1, order_item_id=1)

    async def test_item_from_a_different_order_is_not_found(self):
        """Same cross-order guard as MarkOrderItemOrdered: the item exists,
        just not under this order_id, and that must 404, not leak via a
        permission error checked against the wrong order."""
        order = make_order(id=1)
        orders = FakeOrderRepository([order])
        items = FakeOrderItemRepository([make_order_item(id=1, order_id=2)])
        use_case = MarkOrderItemReadyForPickup(items, orders, uow=FakeUnitOfWork())

        with pytest.raises(OrderItemNotFoundError):
            await use_case.execute(
                actor=make_user(permissions=["write:orders"]), order_id=1, order_item_id=1
            )

    async def test_defaults_to_now_when_no_pickup_at_given(self):
        order = make_order(id=1)
        orders = FakeOrderRepository([order])
        items = FakeOrderItemRepository(
            [make_order_item(id=1, order_id=1, status=OrderItemStatus.ORDERED)]
        )
        use_case = MarkOrderItemReadyForPickup(items, orders, uow=FakeUnitOfWork())

        before = datetime.now(UTC)
        result = await use_case.execute(
            actor=make_user(permissions=["write:orders"]), order_id=1, order_item_id=1
        )
        after = datetime.now(UTC)

        assert result.ready_for_pickup_date is not None
        assert before <= result.ready_for_pickup_date <= after
        assert (await items.get_by_id(1)).changes[-1].endswith("Marked as ready for pickup.")

    async def test_a_line_not_yet_ordered_is_refused(self):
        orders = FakeOrderRepository([make_order(id=1)])
        items = FakeOrderItemRepository([make_order_item(id=1, order_id=1)])
        use_case = MarkOrderItemReadyForPickup(items, orders, uow=FakeUnitOfWork())

        with pytest.raises(OrderItemNotReadyForPickupError):
            await use_case.execute(
                actor=make_user(permissions=["write:orders"]), order_id=1, order_item_id=1
            )

        assert (await items.get_by_id(1)).ready_for_pickup_date is None

    async def test_a_pickup_still_to_come_is_refused(self):
        orders = FakeOrderRepository([make_order(id=1)])
        items = FakeOrderItemRepository(
            [make_order_item(id=1, order_id=1, status=OrderItemStatus.ORDERED)]
        )
        use_case = MarkOrderItemReadyForPickup(items, orders, uow=FakeUnitOfWork())

        with pytest.raises(PickupInFutureError):
            await use_case.execute(
                actor=make_user(permissions=["write:orders"]),
                order_id=1,
                order_item_id=1,
                pickup_at=datetime.now(UTC) + timedelta(days=1),
            )

    async def test_naive_pickup_at_is_read_as_utc(self):
        order = make_order(id=1)
        orders = FakeOrderRepository([order])
        items = FakeOrderItemRepository(
            [make_order_item(id=1, order_id=1, status=OrderItemStatus.ORDERED)]
        )
        use_case = MarkOrderItemReadyForPickup(items, orders, uow=FakeUnitOfWork())
        naive = datetime(2026, 3, 1, 10, 0, 0)

        result = await use_case.execute(
            actor=make_user(permissions=["write:orders"]),
            order_id=1,
            order_item_id=1,
            pickup_at=naive,
        )

        assert result.ready_for_pickup_date == datetime(2026, 3, 1, 10, 0, 0, tzinfo=UTC)

    async def test_aware_pickup_at_is_kept_as_given_for_backdating(self):
        order = make_order(id=1)
        orders = FakeOrderRepository([order])
        items = FakeOrderItemRepository(
            [make_order_item(id=1, order_id=1, status=OrderItemStatus.ORDERED)]
        )
        use_case = MarkOrderItemReadyForPickup(items, orders, uow=FakeUnitOfWork())
        backdated = datetime(2026, 1, 1, 8, 30, tzinfo=UTC)

        result = await use_case.execute(
            actor=make_user(permissions=["write:orders"]),
            order_id=1,
            order_item_id=1,
            pickup_at=backdated,
        )

        assert result.ready_for_pickup_date == backdated

    async def test_no_lot_position_skips_schedule_recompute_without_error(self):
        """lot_repo/production_order_repo/recompute_schedule are all
        optional; an item with no lot_position_id must not need any of
        them, this test passes None for every one of them."""
        order = make_order(id=1)
        orders = FakeOrderRepository([order])
        item = make_order_item(id=1, order_id=1, status=OrderItemStatus.ORDERED)
        assert item.lot_position_id is None
        items = FakeOrderItemRepository([item])
        use_case = MarkOrderItemReadyForPickup(
            items,
            orders,
            lot_repo=None,
            production_order_repo=None,
            recompute_schedule=None,
            uow=FakeUnitOfWork(),
        )

        result = await use_case.execute(
            actor=make_user(permissions=["write:orders"]), order_id=1, order_item_id=1
        )

        assert result.id == 1
