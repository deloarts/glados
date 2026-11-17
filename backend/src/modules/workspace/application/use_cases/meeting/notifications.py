"""
The bundled mentions and todo assignments of a meeting reach their
recipient as one in-app notification and one entry of the e-mail digest,
which the digest sends when the admin settings enable notification mails.
Both show the title and the sentence the event carries, which are already
in the recipient's language.
Registered at startup through src/bootstrap/registrations.py.
"""

from src.modules.platform.application.services.notification_rules import NotificationRule
from src.modules.platform.application.services.notification_rules import NotificationSender
from src.modules.platform.domain.entities.email_notification import EmailNotification
from src.modules.platform.domain.entities.notification import make_notification
from src.modules.platform.domain.value_objects.notification_type import NotificationType
from src.modules.workspace.domain.events.meeting_events import MeetingActivityDue
from src.shared_kernel.domain.events.base import DomainEvent


async def _on_meeting_activity(
    sender: NotificationSender, event: MeetingActivityDue, source_event_id: str
) -> None:
    await sender.notify(
        make_notification(
            user_id=event.recipient_id,
            type=(
                NotificationType.MEETING_TODO_ASSIGNED
                if event.todo_count
                else NotificationType.MEETING_MENTIONED
            ),
            title=event.title or f"Activity in {event.meeting_number}",
            message=f"{event.message}.",
            meeting_id=event.meeting_id,
            source_event_id=source_event_id,
        )
    )
    await sender.queue_digest(
        EmailNotification(
            id=0,
            reason="meeting",
            receiver_id=event.recipient_id,
            demand_item_id=None,
            order_item_id=None,
            meeting_id=event.meeting_id,
            message=f"{event.message}.",
        )
    )


MEETING_NOTIFICATION_RULES: dict[type[DomainEvent], NotificationRule] = {
    MeetingActivityDue: _on_meeting_activity,
}
