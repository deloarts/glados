"""
Who learns about a canceled order and about pieces rejected on delivery.
Registered at startup through src/bootstrap/registrations.py.
"""

from src.modules.fulfillment.domain.events.order_events import DeliveryPiecesRejected
from src.modules.fulfillment.domain.events.order_events import OrderCanceled
from src.modules.platform.application.services.notification_rules import NotificationRule
from src.modules.platform.application.services.notification_rules import NotificationSender
from src.modules.platform.domain.entities.notification import make_notification
from src.modules.platform.domain.value_objects.notification_type import NotificationType
from src.modules.platform.domain.value_objects.permission import Permission
from src.shared_kernel.domain.events.base import DomainEvent


async def _on_order_canceled(
    sender: NotificationSender, event: OrderCanceled, source_event_id: str
) -> None:
    if event.actor_id != event.creator_id:
        await sender.notify(
            make_notification(
                user_id=event.creator_id,
                type=NotificationType.ORDER_CANCELED,
                title="Order canceled",
                message=f"Order {event.order_number} has been canceled.",
                order_id=event.order_id,
                source_event_id=source_event_id,
            )
        )


async def _on_delivery_pieces_rejected(
    sender: NotificationSender, event: DeliveryPiecesRejected, source_event_id: str
) -> None:
    message = (
        f"{event.quantity:.3f} piece(s) rejected on order item #{event.order_item_id}: "
        f"{event.reason} ({event.outcome})."
    )
    for user in await sender.users_with_permission(Permission.WRITE_ORDERS):
        await sender.notify(
            make_notification(
                user_id=user.id,
                type=NotificationType.DELIVERY_PIECES_REJECTED,
                title="Delivery pieces rejected",
                message=message,
                order_id=event.order_id,
                source_event_id=source_event_id,
            )
        )


ORDER_NOTIFICATION_RULES: dict[type[DomainEvent], NotificationRule] = {
    OrderCanceled: _on_order_canceled,
    DeliveryPiecesRejected: _on_delivery_pieces_rejected,
}
