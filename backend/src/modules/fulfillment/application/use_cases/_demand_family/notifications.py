"""
The notifications every demand family sends its creator: a delivery mail and
an in-app note when a demand that asked for it is fulfilled, and an in-app
note when someone else canceled it. Registered at startup through
src/bootstrap/registrations.py.
"""

from src.modules.catalogue.domain.events.bought_item_events import DemandItemStatusChanged
from src.modules.catalogue.domain.events.made_item_events import MadeItemDemandItemStatusChanged
from src.modules.catalogue.domain.value_objects.bought_item_status import BoughtItemDemandStatus
from src.modules.catalogue.domain.value_objects.made_item_status import MadeItemDemandStatus
from src.modules.fulfillment.domain.events.source_item_demand_events import (
    SourceItemDemandStatusChanged,
)
from src.modules.fulfillment.domain.value_objects.source_item_demand_status import (
    SourceItemDemandStatus,
)
from src.modules.platform.application.services.notification_rules import NotificationRule
from src.modules.platform.application.services.notification_rules import NotificationSender
from src.modules.platform.domain.entities.email_notification import EmailNotification
from src.modules.platform.domain.entities.notification import make_notification
from src.modules.platform.domain.value_objects.notification_type import NotificationType
from src.shared_kernel.domain.events.base import DomainEvent


async def _on_demand_status_changed(
    sender: NotificationSender, event: DemandItemStatusChanged, source_event_id: str
) -> None:
    await _notify_demand_creator(
        sender,
        fulfilled=event.new_status == BoughtItemDemandStatus.FULFILLED and event.notify_on_delivery,
        canceled_by_other=event.new_status == BoughtItemDemandStatus.CANCELED
        and event.actor_id != event.creator_id,
        creator_id=event.creator_id,
        demand_id=event.demand_id,
        order_item_id=event.order_item_id,
        item_name=event.item_article_name,
        source_event_id=source_event_id,
    )


async def _on_made_item_demand_status_changed(
    sender: NotificationSender, event: MadeItemDemandItemStatusChanged, source_event_id: str
) -> None:
    await _notify_demand_creator(
        sender,
        fulfilled=event.new_status == MadeItemDemandStatus.FULFILLED and event.notify_on_delivery,
        canceled_by_other=event.new_status == MadeItemDemandStatus.CANCELED
        and event.actor_id != event.creator_id,
        creator_id=event.creator_id,
        demand_id=event.demand_id,
        order_item_id=None,
        item_name=event.item_article_name,
        source_event_id=source_event_id,
    )


async def _on_source_item_demand_status_changed(
    sender: NotificationSender, event: SourceItemDemandStatusChanged, source_event_id: str
) -> None:
    """A lot's raw material demand notifies its creator like the other
    demand families: on delivery when asked to, and when someone else
    canceled it."""
    await _notify_demand_creator(
        sender,
        fulfilled=event.new_status == SourceItemDemandStatus.FULFILLED and event.notify_on_delivery,
        canceled_by_other=event.new_status == SourceItemDemandStatus.CANCELED
        and event.actor_id != event.creator_id,
        creator_id=event.creator_id,
        demand_id=event.demand_id,
        order_item_id=None,
        item_name=event.material_name,
        source_event_id=source_event_id,
    )


async def _notify_demand_creator(
    sender: NotificationSender,
    *,
    fulfilled: bool,
    canceled_by_other: bool,
    creator_id: int,
    demand_id: int,
    order_item_id: int | None,
    item_name: str,
    source_event_id: str,
) -> None:
    """The notifications every demand family sends its creator: a
    delivery mail and an in-app note when a demand that asked for it is
    fulfilled, and an in-app note when someone else canceled it."""
    if fulfilled:
        await sender.queue_digest(
            EmailNotification(
                id=0,
                reason="delivered",
                receiver_id=creator_id,
                demand_item_id=demand_id,
                order_item_id=order_item_id,
            )
        )
        await sender.notify(
            make_notification(
                user_id=creator_id,
                type=NotificationType.DEMAND_ITEM_FULFILLED,
                title="Item delivered",
                message=f"Your demand for '{item_name}' has been fulfilled.",
                demand_item_id=demand_id,
                source_event_id=source_event_id,
            )
        )
    elif canceled_by_other:
        await sender.notify(
            make_notification(
                user_id=creator_id,
                type=NotificationType.DEMAND_ITEM_CANCELED,
                title="Demand canceled",
                message=f"Your demand for '{item_name}' has been canceled.",
                demand_item_id=demand_id,
                source_event_id=source_event_id,
            )
        )


DEMAND_NOTIFICATION_RULES: dict[type[DomainEvent], NotificationRule] = {
    DemandItemStatusChanged: _on_demand_status_changed,
    MadeItemDemandItemStatusChanged: _on_made_item_demand_status_changed,
    SourceItemDemandStatusChanged: _on_source_item_demand_status_changed,
}
