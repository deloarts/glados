"""
The designated user of a project learns that it was assigned to them, in the
app and by mail. Registered at startup through
src/bootstrap/registrations.py.
"""

from src.modules.platform.application.services.notification_rules import NotificationRule
from src.modules.platform.application.services.notification_rules import NotificationSender
from src.modules.platform.domain.entities.notification import make_notification
from src.modules.platform.domain.value_objects.mail_template_kind import MailTemplateKind
from src.modules.platform.domain.value_objects.notification_type import NotificationType
from src.modules.workspace.domain.events.project_events import ProjectCreated
from src.modules.workspace.domain.events.project_events import ProjectUpdated
from src.shared_kernel.domain.events.base import DomainEvent


async def _on_project_assigned(
    sender: NotificationSender, event: ProjectCreated | ProjectUpdated, source_event_id: str
) -> None:
    if (
        isinstance(event, ProjectUpdated)
        and event.designated_user_id == event.old_designated_user_id
    ):
        return
    if event.designated_user_id == event.actor_id:
        return
    await sender.notify(
        make_notification(
            user_id=event.designated_user_id,
            type=NotificationType.PROJECT_ASSIGNED,
            title="Project assigned",
            message=(
                f"You have been assigned as the designated user for project {event.project_number}."
            ),
            project_id=event.project_id,
            source_event_id=source_event_id,
        )
    )
    await sender.commit()
    await sender.mail_active_user(
        MailTemplateKind.PROJECT_ASSIGNED,
        event.designated_user_id,
        project_number=event.project_number,
    )


PROJECT_NOTIFICATION_RULES: dict[type[DomainEvent], NotificationRule] = {
    ProjectCreated: _on_project_assigned,
    ProjectUpdated: _on_project_assigned,
}
