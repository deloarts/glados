"""
Who learns that a controlled document's edit lock was taken over or ended,
that a revision was marked invalid, or that a new revision was started.
Registered at startup through src/bootstrap/registrations.py.
"""

from src.modules.platform.application.services.notification_rules import NotificationRule
from src.modules.platform.application.services.notification_rules import NotificationSender
from src.modules.platform.domain.entities.notification import make_notification
from src.modules.platform.domain.value_objects.notification_type import NotificationType
from src.modules.quality.domain.events.document_events import DocumentEditingEnded
from src.modules.quality.domain.events.document_events import DocumentEditingTakenOver
from src.modules.quality.domain.events.document_events import DocumentMarkedInvalid
from src.modules.quality.domain.events.document_events import DocumentRevised
from src.shared_kernel.domain.events.base import DomainEvent


async def _on_editing_taken_over(
    sender: NotificationSender, event: DocumentEditingTakenOver, source_event_id: str
) -> None:
    await sender.notify(
        make_notification(
            user_id=event.previous_editor_id,
            type=NotificationType.EDITING_TAKEN_OVER,
            title="Editing taken over",
            message=(
                f"{event.actor_name} took over editing of {event.title!r}. "
                "Changes you had not saved were not kept."
            ),
            source_event_id=source_event_id,
        )
    )


async def _on_editing_ended(
    sender: NotificationSender, event: DocumentEditingEnded, source_event_id: str
) -> None:
    await sender.notify(
        make_notification(
            user_id=event.previous_editor_id,
            type=NotificationType.EDITING_ENDED,
            title="Editing ended",
            message=(
                f"{event.actor_name} ended your editing of {event.title!r}. "
                "Changes you had not saved were not kept."
            ),
            source_event_id=source_event_id,
        )
    )


async def _on_document_marked_invalid(
    sender: NotificationSender, event: DocumentMarkedInvalid, source_event_id: str
) -> None:
    for user_id in sorted(set(event.recipient_ids) - {event.actor_id}):
        await sender.notify(
            make_notification(
                user_id=user_id,
                type=NotificationType.DOCUMENT_MARKED_INVALID,
                title="Revision marked invalid",
                message=(
                    f"{event.actor_name} marked revision {event.revision} of "
                    f"{event.title!r} invalid: {event.reason}"
                ),
                source_event_id=source_event_id,
            )
        )


async def _on_document_revised(
    sender: NotificationSender, event: DocumentRevised, source_event_id: str
) -> None:
    for user_id in sorted(set(event.recipient_ids) - {event.actor_id}):
        await sender.notify(
            make_notification(
                user_id=user_id,
                type=NotificationType.DOCUMENT_REVISED,
                title="New revision started",
                message=(
                    f"{event.actor_name} started revision {event.revision} of "
                    f"{event.title!r} from revision {event.previous_revision}: "
                    f"{event.reason}"
                ),
                source_event_id=source_event_id,
            )
        )


DOCUMENT_NOTIFICATION_RULES: dict[type[DomainEvent], NotificationRule] = {
    DocumentEditingTakenOver: _on_editing_taken_over,
    DocumentEditingEnded: _on_editing_ended,
    DocumentMarkedInvalid: _on_document_marked_invalid,
    DocumentRevised: _on_document_revised,
}
