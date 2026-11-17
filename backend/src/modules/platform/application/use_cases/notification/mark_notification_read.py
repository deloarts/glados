"""
Marks a user's in-app notifications as read. MarkNotificationRead flips a
single notification, restricted to its own owner (or the system user);
MarkAllNotificationsRead clears every unread notification for the calling
actor in one call.
"""

from src.modules.platform.application.services.lookup import found_or_raise
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.exceptions import InsufficientPermissionsError
from src.modules.platform.domain.exceptions import NotificationNotFoundError
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.ports.outbound.repositories.notification_repository import (
    INotificationRepository,
)
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork


class MarkNotificationRead:
    def __init__(self, notification_repo: INotificationRepository, *, uow: IUnitOfWork) -> None:
        self._repo = notification_repo
        self._uow = uow

    async def execute(self, actor: User, notification_id: int) -> None:
        notification = found_or_raise(
            await self._repo.get_by_id(notification_id),
            NotificationNotFoundError,
            f"Notification #{notification_id} not found.",
        )
        if notification.user_id != actor.id and not actor.is_systemuser:
            raise InsufficientPermissionsError("You can only mark your own notifications as read.")
        await self._repo.mark_read(notification_id)
        await self._uow.commit()
        log.debug(
            "Notification #%s marked read.",
            notification_id,
        )


class MarkAllNotificationsRead:
    def __init__(self, notification_repo: INotificationRepository, *, uow: IUnitOfWork) -> None:
        self._repo = notification_repo
        self._uow = uow

    async def execute(self, actor: User) -> None:
        await self._repo.mark_all_read(actor.id)
        await self._uow.commit()
        log.debug("All notifications marked read.")
