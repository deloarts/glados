"""
Re-parents an order item to a different order, updating order_id, position, and supplier_id
while keeping lot_position_id and allocations untouched. Only a pending, requested or ordered
line on which nothing was delivered or rejected moves, because received pieces stay on the
order that received them, and never onto an order someone canceled; an order that reads
canceled only because every line is canceled takes it, as it takes a new line. The lifecycle
reconciler derives the status of both orders afterwards.
"""

from datetime import datetime

from src.modules.fulfillment.application.dto.order_dto import OrderItemResult
from src.modules.fulfillment.application.mappers.order_mapper import OrderItemMapper
from src.modules.fulfillment.application.services.lifecycle_reconciler import LifecycleReconciler
from src.modules.fulfillment.domain.entities.order import Order
from src.modules.fulfillment.domain.entities.order_item import OrderItem
from src.modules.fulfillment.domain.errors import OrderItemNotFoundError
from src.modules.fulfillment.domain.errors import OrderNotFoundError
from src.modules.fulfillment.domain.services.order_rules import OrderRules
from src.modules.fulfillment.ports.outbound.repositories.order_repository import (
    IOrderItemRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.order_repository import IOrderRepository
from src.modules.platform.application.services.lookup import found_or_raise
from src.modules.platform.application.services.schedule_recompute_port import ScheduleRecompute
from src.modules.platform.application.services.schedule_recompute_port import (
    recompute_schedule_after_commit,
)
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.services.edit_version import bump_edit_version
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork
from src.shared_kernel.domain.services.changelog_service import append_changelog
from src.shared_kernel.domain.services.clock import now_utc


class MoveOrderItem:
    """
    Re-parents an order item onto a different order. Non-destructive: only
    order_id, position, and supplier_id change. lot_position_id, project_id,
    delivery dates and every allocation (all FK order_item_id, not order_id)
    are left untouched and follow the item. The move rule of the order item
    intent table admits only a line without deliveries or rejections, so no
    delivery row ever changes order.
    """

    def __init__(
        self,
        order_repo: IOrderRepository,
        order_item_repo: IOrderItemRepository,
        *,
        uow: IUnitOfWork,
        reconciler: LifecycleReconciler,
        recompute_schedule: ScheduleRecompute | None = None,
    ) -> None:
        self._orders = order_repo
        self._order_items = order_item_repo
        self._uow = uow
        self._reconciler = reconciler
        self._recompute = recompute_schedule

    async def execute(
        self, actor: User, source_order_id: int, order_item_id: int, target_order_id: int
    ) -> OrderItemResult:
        source, target, item = await self._read(source_order_id, order_item_id, target_order_id)

        # Both orders and the line, in one acquisition before the checks.
        self._reconciler.touch_orders([source_order_id, target_order_id])
        self._reconciler.touch_order_items([order_item_id])
        await self._reconciler.lock_touched()
        source, target, item = await self._read(source_order_id, order_item_id, target_order_id)

        OrderRules.assert_can_move_item(actor, source, target, item)

        now = now_utc()
        old_order_id = item.order_id
        # The line now sits under another order and possibly another
        # supplier, so a client holding its old version is refused.
        bump_edit_version(item)
        item.order_id = target_order_id
        item.position = await self._order_items.next_position(target_order_id)
        item.supplier_id = target.supplier_id
        item.changed = now
        item.changes = append_changelog(
            item.changes,
            actor.full_name,
            f"Moved from order #{old_order_id} to order #{target_order_id}.",
        )
        await self._order_items.save(item)
        if source.supplier_id != target.supplier_id:
            await self._record_supplier_change(actor, source, target, item, now)

        await self._reconciler.run(actor, now)
        await self._uow.commit()
        if source.supplier_id != target.supplier_id:
            # Another supplier's lead time dates the external step it feeds.
            await recompute_schedule_after_commit(
                self._recompute,
                after="moving an order line to another supplier; the change itself is committed.",
            )

        log.info(
            f"Moved order item #{order_item_id} from order "
            f"#{source_order_id} to order #{target_order_id}."
        )

        moved = await self._order_items.get_by_id(order_item_id)
        return OrderItemMapper.to_result(moved or item)

    async def _record_supplier_change(
        self, actor: User, source: Order, target: Order, item: OrderItem, now: datetime
    ) -> None:
        """A line moved to another supplier's order, as when it was booked on
        the wrong order, may already have been sent to the first supplier:
        both orders name the two suppliers, so purchasing can follow up."""
        note = (
            f"Line {item.position} (order item #{item.id}) moved from {source.order_number} "
            f"({_supplier(source)}) to {target.order_number} ({_supplier(target)})."
        )
        for order in (source, target):
            order.changes = append_changelog(order.changes, actor.full_name, note)
            await self._orders.save(order)

    async def _read(
        self, source_order_id: int, order_item_id: int, target_order_id: int
    ) -> tuple[Order, Order, OrderItem]:
        source = found_or_raise(
            await self._orders.get_by_id(source_order_id),
            OrderNotFoundError,
            f"Order #{source_order_id} not found.",
        )

        target = found_or_raise(
            await self._orders.get_by_id(target_order_id),
            OrderNotFoundError,
            f"Order #{target_order_id} not found.",
        )

        item = await self._order_items.get_by_id(order_item_id)
        if not item or item.order_id != source_order_id:
            raise OrderItemNotFoundError(
                f"Order item #{order_item_id} not found in order #{source_order_id}."
            )
        return source, target, item


def _supplier(order: Order) -> str:
    return order.supplier_name or f"supplier #{order.supplier_id}"
