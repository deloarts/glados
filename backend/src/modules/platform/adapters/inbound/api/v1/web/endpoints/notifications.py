"""
In-app notification endpoints. All operations are scoped to the current user,
users can only read, mark, and delete their own notifications.
"""

from fastapi import Depends
from fastapi.routing import APIRouter

from src.modules.platform.adapters.inbound.api.auth_deps import get_current_active_user
from src.modules.platform.adapters.inbound.api.deps.admin import (
    get_clear_all_notifications_use_case,
)
from src.modules.platform.adapters.inbound.api.deps.admin import get_delete_notification_use_case
from src.modules.platform.adapters.inbound.api.deps.admin import (
    get_mark_all_notifications_read_use_case,
)
from src.modules.platform.adapters.inbound.api.deps.admin import get_mark_notification_read_use_case
from src.modules.platform.adapters.inbound.api.deps.admin import get_notifications_use_case
from src.modules.platform.adapters.inbound.api.schemas.notification_schema import (
    NotificationsResponse,
)
from src.modules.platform.application.use_cases.notification.delete_notification import (
    ClearAllNotifications,
)
from src.modules.platform.application.use_cases.notification.delete_notification import (
    DeleteNotification,
)
from src.modules.platform.application.use_cases.notification.get_notifications import (
    GetNotifications,
)
from src.modules.platform.application.use_cases.notification.mark_notification_read import (
    MarkAllNotificationsRead,
)
from src.modules.platform.application.use_cases.notification.mark_notification_read import (
    MarkNotificationRead,
)
from src.modules.platform.domain.entities.user import User

router = APIRouter()


@router.get("/", response_model=NotificationsResponse)
async def read_notifications(
    unread_only: bool = False,
    actor: User = Depends(get_current_active_user),
    use_case: GetNotifications = Depends(get_notifications_use_case),
) -> NotificationsResponse:
    """Return all notifications for the current user."""
    return await use_case.execute(actor=actor, unread_only=unread_only)


@router.patch("/{notification_id}/read", status_code=204)
async def mark_read(
    notification_id: int,
    actor: User = Depends(get_current_active_user),
    use_case: MarkNotificationRead = Depends(get_mark_notification_read_use_case),
) -> None:
    """Mark a single notification as read."""
    await use_case.execute(actor=actor, notification_id=notification_id)


@router.patch("/read-all", status_code=204)
async def mark_all_read(
    actor: User = Depends(get_current_active_user),
    use_case: MarkAllNotificationsRead = Depends(get_mark_all_notifications_read_use_case),
) -> None:
    """Mark all notifications for the current user as read."""
    await use_case.execute(actor=actor)


@router.delete("/{notification_id}", status_code=204)
async def delete_notification(
    notification_id: int,
    actor: User = Depends(get_current_active_user),
    use_case: DeleteNotification = Depends(get_delete_notification_use_case),
) -> None:
    """Delete a single notification."""
    await use_case.execute(actor=actor, notification_id=notification_id)


@router.delete("/", status_code=204)
async def clear_all_notifications(
    actor: User = Depends(get_current_active_user),
    use_case: ClearAllNotifications = Depends(get_clear_all_notifications_use_case),
) -> None:
    """Delete all notifications for the current user."""
    await use_case.execute(actor=actor)
