"""
Marks order items as requested or ordered. A single line is marked requested only from
PENDING and ordered only from PENDING or REQUESTED; any other status is refused with
OrderItemCannotBeMarkedError, and the bulk actions select their lines by the same rule
(order_item_mark_rules.py). A mark records its intent on the line, requested_at or
ordered_date, and the lifecycle reconciler derives the line's and its order's status from
it, and with it the lot position and lot of a MADE line and the demands allocated to the
line, which reach ORDERED once they are fully covered by placed lines.
"""

from datetime import datetime

from src.modules.fulfillment.application.dto.order_dto import OrderItemResult
from src.modules.fulfillment.application.mappers.order_mapper import OrderItemMapper
from src.modules.fulfillment.application.services.lifecycle_reconciler import LifecycleReconciler
from src.modules.fulfillment.application.use_cases.order._lines import lots_of_made_lines
from src.modules.fulfillment.domain.entities.order import Order
from src.modules.fulfillment.domain.entities.order_item import OrderItem
from src.modules.fulfillment.domain.errors import OrderItemNotFoundError
from src.modules.fulfillment.domain.errors import OrderNotFoundError
from src.modules.fulfillment.domain.services.order_item_mark_rules import MARK_ORDERED_SOURCES
from src.modules.fulfillment.domain.services.order_item_mark_rules import MARK_REQUESTED_SOURCES
from src.modules.fulfillment.domain.services.order_item_mark_rules import (
    assert_mark_ordered_allowed,
)
from src.modules.fulfillment.domain.services.order_item_mark_rules import (
    assert_mark_requested_allowed,
)
from src.modules.fulfillment.domain.services.order_rules import OrderRules
from src.modules.fulfillment.domain.value_objects.order_status import OrderItemStatus
from src.modules.fulfillment.ports.outbound.repositories.order_repository import (
    IOrderItemRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.order_repository import IOrderRepository
from src.modules.platform.application.services.lookup import found_or_raise
from src.modules.platform.domain.entities.user import User
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork
from src.shared_kernel.domain.services.changelog_service import append_changelog
from src.shared_kernel.domain.services.clock import now_utc


def record_ordered(item: OrderItem, actor: User, now: datetime, note: str) -> None:
    """Records the ordered intent on a line, its ordered_date, with a
    changelog note. The caller saves the line."""
    item.ordered_date = now
    item.changed = now
    item.changes = append_changelog(item.changes, actor.full_name, note)


def record_requested(item: OrderItem, actor: User, now: datetime, note: str) -> None:
    """Records the requested intent on a line, its requested_at, with a
    changelog note. The caller saves the line."""
    item.requested_at = now
    item.changed = now
    item.changes = append_changelog(item.changes, actor.full_name, note)


async def _line_of(
    order_items: IOrderItemRepository, order_id: int, order_item_id: int
) -> OrderItem:
    """The line, which must belong to the order named in the path: without
    that, a permission check against one order could be satisfied via a
    draft order while an item of a past-draft one is changed. The 404
    deliberately does not confirm the item's real parent."""
    order_item = await order_items.get_by_id(order_item_id)
    if not order_item or order_item.order_id != order_id:
        raise OrderItemNotFoundError(f"Order item #{order_item_id} not found.")
    return order_item


class MarkOrderItemOrdered:
    """Marks a single order item ordered from PENDING or REQUESTED and stamps
    its ordered_date. Any other status is refused with
    OrderItemCannotBeMarkedError."""

    def __init__(
        self,
        order_item_repo: IOrderItemRepository,
        order_repo: IOrderRepository,
        *,
        uow: IUnitOfWork,
        reconciler: LifecycleReconciler,
    ) -> None:
        self._order_items = order_item_repo
        self._orders = order_repo
        self._uow = uow
        self._reconciler = reconciler

    async def execute(self, actor: User, order_id: int, order_item_id: int) -> OrderItemResult:
        order = found_or_raise(
            await self._orders.get_by_id(order_id),
            OrderNotFoundError,
            f"Order #{order_id} not found.",
        )
        order_item = await _line_of(self._order_items, order_id, order_item_id)
        _assert_line_updatable(actor, order, order_item)

        # The lot of a MADE line comes first in the one lock order, because
        # its position and lot are recomputed below.
        self._reconciler.touch_order_items([order_item_id])
        await self._reconciler.lock_touched(also=lots_of_made_lines([order_item]))
        order_item = await _line_of(self._order_items, order_id, order_item_id)
        _assert_line_updatable(actor, await _order_of(self._orders, order_id), order_item)
        assert_mark_ordered_allowed(order_item)

        now = now_utc()
        record_ordered(order_item, actor, now, "Marked as ordered.")
        await self._order_items.save(order_item)
        log.info(f"Marked order item #{order_item_id} as ordered.")

        await self._reconciler.run(actor, now)
        marked = await _line_of(self._order_items, order_id, order_item_id)
        await self._uow.commit()

        return OrderItemMapper.to_result(marked)


class MarkAllOrderItemsOrdered:
    """Marks every PENDING or REQUESTED order item of an order ordered,
    stamping each line's ordered_date. Lines in other statuses are skipped."""

    def __init__(
        self,
        order_item_repo: IOrderItemRepository,
        order_repo: IOrderRepository,
        *,
        uow: IUnitOfWork,
        reconciler: LifecycleReconciler,
    ) -> None:
        self._order_items = order_item_repo
        self._orders = order_repo
        self._uow = uow
        self._reconciler = reconciler

    async def execute(self, actor: User, order_id: int) -> list[OrderItemResult]:
        order = found_or_raise(
            await self._orders.get_by_id(order_id),
            OrderNotFoundError,
            f"Order #{order_id} not found.",
        )
        _assert_open_lines_updatable(actor, order)

        candidates = [
            item
            for item in await self._order_items.get_by_order_id(order_id)
            if item.status in MARK_ORDERED_SOURCES
        ]
        self._reconciler.touch_order_items([item.id for item in candidates])
        await self._reconciler.lock_touched(also=lots_of_made_lines(candidates))
        _assert_open_lines_updatable(actor, await _order_of(self._orders, order_id))

        now = now_utc()
        locked = {item.id for item in candidates}
        marked: list[int] = []
        for item in await self._order_items.get_by_order_id(order_id):
            if item.id not in locked or item.status not in MARK_ORDERED_SOURCES:
                continue
            record_ordered(item, actor, now, "Marked as ordered (bulk action).")
            await self._order_items.save(item)
            marked.append(item.id)
        log.info(f"Marked {len(marked)} order item(s) as ordered in order #{order_id}.")

        await self._reconciler.run(actor, now)
        lines = [
            item for item in await self._order_items.get_by_order_id(order_id) if item.id in marked
        ]
        await self._uow.commit()

        return [OrderItemMapper.to_result(item) for item in lines]


class MarkOrderItemRequested:
    """Marks a single order item requested from PENDING and stamps its
    requested_at. Any other status is refused with
    OrderItemCannotBeMarkedError."""

    def __init__(
        self,
        order_item_repo: IOrderItemRepository,
        order_repo: IOrderRepository,
        *,
        uow: IUnitOfWork,
        reconciler: LifecycleReconciler,
    ) -> None:
        self._order_items = order_item_repo
        self._orders = order_repo
        self._uow = uow
        self._reconciler = reconciler

    async def execute(self, actor: User, order_id: int, order_item_id: int) -> OrderItemResult:
        order = found_or_raise(
            await self._orders.get_by_id(order_id),
            OrderNotFoundError,
            f"Order #{order_id} not found.",
        )
        _assert_line_updatable(
            actor, order, await _line_of(self._order_items, order_id, order_item_id)
        )

        self._reconciler.touch_order_items([order_item_id])
        await self._reconciler.lock_touched()
        order_item = await _line_of(self._order_items, order_id, order_item_id)
        _assert_line_updatable(actor, await _order_of(self._orders, order_id), order_item)
        assert_mark_requested_allowed(order_item)

        now = now_utc()
        record_requested(order_item, actor, now, "Marked as requested.")
        await self._order_items.save(order_item)
        log.info(f"Marked order item #{order_item_id} as requested.")

        await self._reconciler.run(actor, now)
        await self._uow.commit()

        return OrderItemMapper.to_result(await _line_of(self._order_items, order_id, order_item_id))


class MarkAllOrderItemsRequested:
    """Marks every PENDING order item of an order requested, stamping each
    line's requested_at. Lines in other statuses are skipped."""

    def __init__(
        self,
        order_item_repo: IOrderItemRepository,
        order_repo: IOrderRepository,
        *,
        uow: IUnitOfWork,
        reconciler: LifecycleReconciler,
    ) -> None:
        self._order_items = order_item_repo
        self._orders = order_repo
        self._uow = uow
        self._reconciler = reconciler

    async def execute(self, actor: User, order_id: int) -> list[OrderItemResult]:
        order = found_or_raise(
            await self._orders.get_by_id(order_id),
            OrderNotFoundError,
            f"Order #{order_id} not found.",
        )
        _assert_open_lines_updatable(actor, order)

        candidates = [
            item.id
            for item in await self._order_items.get_by_order_id(order_id)
            if item.status in MARK_REQUESTED_SOURCES
        ]
        self._reconciler.touch_order_items(candidates)
        await self._reconciler.lock_touched()
        _assert_open_lines_updatable(actor, await _order_of(self._orders, order_id))

        now = now_utc()
        marked: list[int] = []
        for item in await self._order_items.get_by_order_id(order_id):
            if item.id not in candidates or item.status not in MARK_REQUESTED_SOURCES:
                continue
            record_requested(item, actor, now, "Marked as requested (bulk action).")
            await self._order_items.save(item)
            marked.append(item.id)
        log.info(f"Marked {len(marked)} order item(s) as requested in order #{order_id}.")

        await self._reconciler.run(actor, now)
        await self._uow.commit()

        return [
            OrderItemMapper.to_result(item)
            for item in await self._order_items.get_by_order_id(order_id)
            if item.id in marked
        ]


async def _order_of(orders: IOrderRepository, order_id: int) -> Order:
    """The order read again under the lock its lines' widening took, since
    the first permission check ran on an unlocked read."""
    return found_or_raise(
        await orders.get_by_id(order_id), OrderNotFoundError, f"Order #{order_id} not found."
    )


def _assert_line_updatable(actor: User, order: Order, line: OrderItem) -> None:
    OrderRules.assert_can_update_line(actor, order, line.status, f"Order item #{line.id}")


def _assert_open_lines_updatable(actor: User, order: Order) -> None:
    """A bulk mark touches only PENDING and REQUESTED lines, so the order's
    lines that the supplier does not hold yet decide the permission."""
    OrderRules.assert_can_update_line(
        actor, order, OrderItemStatus.PENDING, f"The open lines of order #{order.id}"
    )
