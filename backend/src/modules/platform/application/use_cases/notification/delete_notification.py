"""
Delete a specific notification or clear all notifications for the
current user.
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


class DeleteNotification:
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
            raise InsufficientPermissionsError("You can only delete your own notifications.")
        await self._repo.delete_by_id(notification_id)
        await self._uow.commit()
        log.debug(
            "Notification #%s deleted.",
            notification_id,
        )


class ClearAllNotifications:
    def __init__(self, notification_repo: INotificationRepository, *, uow: IUnitOfWork) -> None:
        self._repo = notification_repo
        self._uow = uow

    async def execute(self, actor: User) -> None:
        await self._repo.delete_all_by_user_id(actor.id)
        await self._uow.commit()
        log.debug("All notifications cleared.")
