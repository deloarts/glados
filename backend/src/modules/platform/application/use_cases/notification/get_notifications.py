"""
Retrieve notifications for the current user, optionally filtered to
unread only.
"""

from src.modules.platform.application.dto.notification_dto import NotificationResult
from src.modules.platform.application.dto.notification_dto import NotificationsResponse
from src.modules.platform.application.mappers.notification_mapper import NotificationMapper
from src.modules.platform.domain.entities.user import User
from src.modules.platform.ports.outbound.repositories.notification_repository import (
    INotificationRepository,
)


class GetNotifications:
    def __init__(self, notification_repo: INotificationRepository) -> None:
        self._repo = notification_repo

    async def execute(self, actor: User, unread_only: bool = False) -> NotificationsResponse:
        notifications = await self._repo.get_by_user_id(actor.id, unread_only=unread_only)
        unread_count = await self._repo.get_unread_count(actor.id)
        items: list[NotificationResult] = [NotificationMapper.to_result(n) for n in notifications]
        return NotificationsResponse(
            total=len(items),
            unread_count=unread_count,
            items=items,
        )
