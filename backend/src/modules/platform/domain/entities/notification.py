"""
In-app notification record. Created by use cases when meaningful events occur
(delivery, permission changes, etc.) and consumed by the UI notification panel.
"""

from dataclasses import dataclass
from datetime import datetime

from src.modules.platform.domain.value_objects.notification_type import NotificationType
from src.shared_kernel.domain.entities.base import Entity
from src.shared_kernel.domain.services.clock import now_utc


@dataclass
class Notification(Entity):
    user_id: int  # recipient
    type: NotificationType
    title: str
    message: str
    is_read: bool
    created_at: datetime

    # Optional context links, only the relevant one is set
    demand_item_id: int | None = None
    order_id: int | None = None
    project_id: int | None = None
    product_id: int | None = None
    meeting_id: int | None = None

    # Event bus message ID that produced this notification, used by the
    # notification consumer to skip already-handled redeliveries.
    source_event_id: str | None = None


def make_notification(
    user_id: int,
    type: NotificationType,
    title: str,
    message: str,
    *,
    demand_item_id: int | None = None,
    order_id: int | None = None,
    project_id: int | None = None,
    product_id: int | None = None,
    meeting_id: int | None = None,
    source_event_id: str | None = None,
) -> Notification:
    # Context links are exclusive: at most one names the entity this
    # notification is a deep-link to, see the Notification docstring. A
    # violation degrades a UI deep-link, not data integrity (unlike other
    # catalogue checks, there is no DB CHECK constraint here), but is
    # still a caller bug worth catching at construction time.
    offenders = [
        name
        for name, value in (
            ("demand_item_id", demand_item_id),
            ("order_id", order_id),
            ("project_id", project_id),
            ("product_id", product_id),
            ("meeting_id", meeting_id),
        )
        if value is not None
    ]
    assert len(offenders) <= 1, (
        f"Notification context links are exclusive; got more than one set: {offenders}."
    )
    return Notification(
        id=0,
        user_id=user_id,
        type=type,
        title=title,
        message=message,
        is_read=False,
        created_at=now_utc(),
        demand_item_id=demand_item_id,
        order_id=order_id,
        project_id=project_id,
        product_id=product_id,
        meeting_id=meeting_id,
        source_event_id=source_event_id,
    )
