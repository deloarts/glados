"""Deliver-all: books every line of an order that can take a delivery in one
transaction, through the booking steps of ProcessOrderItemDelivery, and
reports the other lines with the reason they were skipped.

ProcessOrderItemDelivery is imported for type checking only, because
process_order_item_delivery.py imports this module to keep DeliverAllOrderItems
importable from there.
"""

from typing import TYPE_CHECKING

from src.modules.fulfillment.application.dto.order_dto import DeliverAllResult
from src.modules.fulfillment.application.dto.order_dto import DeliverAllSkippedLine
from src.modules.fulfillment.application.dto.order_dto import DeliveryRejectionInput
from src.modules.fulfillment.application.mappers.order_mapper import OrderItemMapper
from src.modules.fulfillment.application.services.lifecycle_loader import AggregateIds
from src.modules.fulfillment.application.services.lifecycle_reconciler import LifecycleReconciler
from src.modules.fulfillment.application.use_cases.order._lines import lots_of_made_lines
from src.modules.fulfillment.application.use_cases.production_schedule.recompute_machine_schedule import (
    RecomputeMachineSchedule,
)
from src.modules.fulfillment.domain.entities.order import Order
from src.modules.fulfillment.domain.entities.order_item import OrderItem
from src.modules.fulfillment.domain.errors import OrderItemNotDeliverableError
from src.modules.fulfillment.domain.errors import OrderItemNotFoundError
from src.modules.fulfillment.domain.errors import OrderNotFoundError
from src.modules.fulfillment.domain.services.delivery_booking_rules import deliver_all_skip_reason
from src.modules.fulfillment.domain.services.delivery_booking_rules import is_open_for_delivery
from src.modules.fulfillment.domain.services.delivery_booking_rules import loses_made_pieces
from src.modules.fulfillment.domain.services.order_rules import OrderRules
from src.modules.fulfillment.domain.value_objects.lifecycle_aggregate import LifecycleAggregate
from src.modules.fulfillment.domain.value_objects.material_receipt import MaterialReceipt
from src.modules.fulfillment.ports.outbound.repositories.order_repository import (
    IOrderItemRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.order_repository import IOrderRepository
from src.modules.platform.application.services.lookup import found_or_raise
from src.modules.platform.application.services.schedule_recompute_port import (
    recompute_schedule_after_commit,
)
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.exceptions import ConcurrentModificationError
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.ports.outbound.event_bus_port import IEventBus
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork
from src.shared_kernel.domain.services.clock import now_utc

if TYPE_CHECKING:
    from src.modules.fulfillment.application.use_cases.order.process_order_item_delivery import (
        DeliveryBooking,
    )
    from src.modules.fulfillment.application.use_cases.order.process_order_item_delivery import (
        ProcessOrderItemDelivery,
    )


class DeliverAllOrderItems:
    """Delivers every line of an order that can take a delivery, by the rule
    a single delivery enforces, and reports the others with the reason they
    were skipped, so a line marked ordered on a draft order is delivered as
    a single delivery would be. Only the lines still open are locked. A line
    that a move put on another order while this request waited for the
    locks is skipped as moved. A rejection named for a line not on the order
    is refused with OrderItemNotFoundError, one for a line that takes no
    delivery with OrderItemNotDeliverableError, instead of being dropped,
    and one for a line moved meanwhile with ConcurrentModificationError. When no line can
    take a delivery nothing is committed. Every booking runs in one
    transaction, so a line that fails books nothing on the other lines
    either. The permission is checked up front, so a forbidden actor fails
    before any item is touched.
    """

    def __init__(
        self,
        order_repo: IOrderRepository,
        order_item_repo: IOrderItemRepository,
        delivery_use_case: "ProcessOrderItemDelivery",
        *,
        event_bus: IEventBus,
        uow: IUnitOfWork,
        reconciler: LifecycleReconciler,
        recompute_schedule: RecomputeMachineSchedule | None = None,
    ) -> None:
        self._orders = order_repo
        self._order_items = order_item_repo
        self._deliver = delivery_use_case
        self._bus = event_bus
        self._uow = uow
        self._reconciler = reconciler
        self._recompute = recompute_schedule

    async def execute(
        self,
        actor: User,
        order_id: int,
        storage_place: str | None = None,
        rejections: list[DeliveryRejectionInput] | None = None,
        delivery_note_number: str | None = None,
        damage_noted_on_delivery_note: bool = False,
    ) -> DeliverAllResult:
        """`delivery_note_number` is the shipment's delivery note, recorded on
        every delivery row it books together with whether damage was noted
        on it at handover."""
        OrderRules.assert_can_receive_delivery(actor)
        if not await self._orders.get_by_id(order_id):
            raise OrderNotFoundError(f"Order #{order_id} not found.")

        # The order, every line of it and the lots of its MADE lines, in one
        # acquisition, so the whole order is booked under one set of locks;
        # when a rejection loses pieces of a lot, the lots come first alone
        # and their work joins it. The demands allocated on those lines and
        # lots join the same acquisition, with their neighbours, since a
        # booking refits their allocations and the run derives them. Only
        # the lines booked below are touched, so the reconciler derives no
        # line that took no delivery.
        lines = await self._order_items.get_by_order_id(order_id)
        rejections_by_item_id = {r.order_item_id: r for r in rejections or []}
        unknown = sorted(set(rejections_by_item_id) - {line.id for line in lines})
        if unknown:
            raise OrderItemNotFoundError(
                f"Order item #{unknown[0]} not found in order #{order_id}; its rejection "
                "cannot be booked."
            )
        locked = await self._lock_order(order_id, lines, rejections_by_item_id)
        order = found_or_raise(
            await self._orders.get_by_id(order_id),
            OrderNotFoundError,
            f"Order #{order_id} not found.",
        )

        # Each line is judged by the single delivery rule, read under the
        # lock; lines without a rejection get their full remainder.
        now = now_utc()
        bookings: list[DeliveryBooking] = []
        skipped: list[DeliverAllSkippedLine] = []
        # Pieces accepted per lot position by the bookings so far: a MADE
        # line's position feeds the next one before the run stores them.
        accepted: dict[int, float] = {}
        # The locked lines once more, in one read: the lock re-read their
        # columns, this read their relations too.
        current = {
            line.id: line
            for line in await self._order_items.get_by_ids(sorted(locked), refresh=True)
        }
        for line in lines:
            item = current.get(line.id, line)
            rejection = rejections_by_item_id.get(item.id)
            skip = await self._skipped_line(order, item, rejection, locked)
            if skip is not None:
                skipped.append(skip)
                continue
            bookings.append(
                await self._deliver.book(
                    actor,
                    item.id,
                    now,
                    storage_place=storage_place,
                    quantity_rejected=rejection.quantity_rejected if rejection else 0.0,
                    rejection_reason=rejection.rejection_reason if rejection else None,
                    rejection_note=rejection.rejection_note if rejection else None,
                    rejection_outcome=rejection.rejection_outcome if rejection else None,
                    create_replacement=rejection.create_replacement if rejection else True,
                    accepted_earlier=accepted,
                    locked=(order, item),
                    material=MaterialReceipt(
                        delivery_note_number=delivery_note_number,
                        damage_noted_on_delivery_note=damage_noted_on_delivery_note,
                    ),
                )
            )
            self._reconciler.touch_order_items([item.id])
        if not bookings:
            log.info(f"No order item of order #{order_id} could take a delivery.")
            return DeliverAllResult(skipped=skipped)

        result = await self._reconciler.run(actor, now)
        effects = await self._deliver.apply_effects(actor, bookings, result)
        for event in effects.events:
            await self._bus.publish(event)
        await self._uow.commit()

        await recompute_schedule_after_commit(
            self._recompute,
            after=(f"delivering order #{order_id}; the deliveries themselves are committed."),
        )

        log.info(
            f"Bulk-delivered {len(bookings)} order item(s) in order #{order_id}. "
            f"Fulfilled {effects.fulfilled_count} demand(s)."
        )
        delivered = {booking.order_item_id for booking in bookings}
        return DeliverAllResult(
            delivered=[
                OrderItemMapper.to_result(item)
                for item in await self._order_items.get_by_order_id(order_id)
                if item.id in delivered
            ],
            skipped=skipped,
        )

    async def _lock_order(
        self,
        order_id: int,
        lines: list[OrderItem],
        rejections_by_item_id: dict[int, DeliveryRejectionInput],
    ) -> set[int]:
        """Locks the order with its open lines, the lots of its MADE lines and
        the demands allocated on both, and returns the ids of the lines it
        locked. When a rejection loses pieces of a lot, the lots' work joins
        the acquisition too."""
        locked = {
            line.id
            for line in lines
            if is_open_for_delivery(line) or line.id in rejections_by_item_id
        }
        lots = lots_of_made_lines(lines)
        loses_lot_pieces = any(
            loses_made_pieces(line, r.quantity_rejected, r.rejection_outcome)
            for line in lines
            if (r := rejections_by_item_id.get(line.id)) is not None
        )
        work = await self._deliver.lot_work_targets(lots) if loses_lot_pieces else AggregateIds()
        self._reconciler.touch_allocations_on(
            order_item_ids=locked, lot_ids=lots.get(LifecycleAggregate.LOTS)
        )
        await self._reconciler.lock_touched(
            also=AggregateIds.of(
                {
                    LifecycleAggregate.ORDERS: {order_id},
                    LifecycleAggregate.ORDER_ITEMS: locked,
                }
            ).union(lots.union(work))
        )
        return locked

    async def _skipped_line(
        self,
        order: Order,
        item: OrderItem,
        rejection: DeliveryRejectionInput | None,
        locked: set[int],
    ) -> DeliverAllSkippedLine | None:
        """Why the line takes no delivery, or None when it takes one. A line
        that cannot take its rejection is refused instead of skipped."""
        # A move that committed while this request waited for the locks put
        # the line on an order this request has not locked.
        if item.order_id != order.id:
            if rejection is not None:
                raise ConcurrentModificationError(
                    f"Order item #{item.id} was moved to another order while its "
                    "rejection was waiting to be booked. Reload and try again."
                )
            return DeliverAllSkippedLine(
                order_item_id=item.id, position=item.position, reason="moved"
            )
        if item.id not in locked or not await self._deliver.can_deliver(order, item):
            if rejection is not None:
                raise OrderItemNotDeliverableError(
                    f"Order item #{item.id} takes no delivery (status={item.status.value}); its "
                    "rejection cannot be booked."
                )
            return DeliverAllSkippedLine(
                order_item_id=item.id,
                position=item.position,
                reason=deliver_all_skip_reason(order, item),
            )
        return None
