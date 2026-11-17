"""
The designated user of a product learns that it was assigned to them, in the
app and by mail. Registered at startup through
src/bootstrap/registrations.py.
"""

from src.modules.platform.application.services.notification_rules import NotificationRule
from src.modules.platform.application.services.notification_rules import NotificationSender
from src.modules.platform.domain.entities.notification import make_notification
from src.modules.platform.domain.value_objects.mail_template_kind import MailTemplateKind
from src.modules.platform.domain.value_objects.notification_type import NotificationType
from src.modules.workspace.domain.events.product_events import ProductCreated
from src.modules.workspace.domain.events.product_events import ProductUpdated
from src.shared_kernel.domain.events.base import DomainEvent


async def _on_product_assigned(
    sender: NotificationSender, event: ProductCreated | ProductUpdated, source_event_id: str
) -> None:
    if (
        isinstance(event, ProductUpdated)
        and event.designated_user_id == event.old_designated_user_id
    ):
        return
    if event.designated_user_id == event.actor_id:
        return
    await sender.notify(
        make_notification(
            user_id=event.designated_user_id,
            type=NotificationType.PRODUCT_ASSIGNED,
            title="Product assigned",
            message=(
                f"You have been assigned as the designated user for product {event.product_number}."
            ),
            product_id=event.product_id,
            source_event_id=source_event_id,
        )
    )
    await sender.commit()
    await sender.mail_active_user(
        MailTemplateKind.PRODUCT_ASSIGNED,
        event.designated_user_id,
        product_number=event.product_number,
    )


PRODUCT_NOTIFICATION_RULES: dict[type[DomainEvent], NotificationRule] = {
    ProductCreated: _on_product_assigned,
    ProductUpdated: _on_product_assigned,
}
