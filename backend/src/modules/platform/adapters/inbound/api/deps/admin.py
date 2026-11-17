"""Use case factories: in-app notifications, log entries."""

from fastapi import Depends

from src.modules.platform.adapters.inbound.api.deps.database import get_unit_of_work
from src.modules.platform.adapters.inbound.api.deps.repositories import get_inapp_notification_repo
from src.modules.platform.adapters.inbound.api.deps.repositories import get_log_repo
from src.modules.platform.application.use_cases.log.get_log_entries import GetLogEntries
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
from src.modules.platform.ports.outbound.repositories.log_repository import ILogRepository
from src.modules.platform.ports.outbound.repositories.notification_repository import (
    INotificationRepository,
)
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork


def get_notifications_use_case(
    notification_repo: INotificationRepository = Depends(get_inapp_notification_repo),
) -> GetNotifications:
    return GetNotifications(notification_repo=notification_repo)


def get_mark_notification_read_use_case(
    notification_repo: INotificationRepository = Depends(get_inapp_notification_repo),
    uow: IUnitOfWork = Depends(get_unit_of_work),
) -> MarkNotificationRead:
    return MarkNotificationRead(notification_repo=notification_repo, uow=uow)


def get_mark_all_notifications_read_use_case(
    notification_repo: INotificationRepository = Depends(get_inapp_notification_repo),
    uow: IUnitOfWork = Depends(get_unit_of_work),
) -> MarkAllNotificationsRead:
    return MarkAllNotificationsRead(notification_repo=notification_repo, uow=uow)


def get_delete_notification_use_case(
    notification_repo: INotificationRepository = Depends(get_inapp_notification_repo),
    uow: IUnitOfWork = Depends(get_unit_of_work),
) -> DeleteNotification:
    return DeleteNotification(notification_repo=notification_repo, uow=uow)


def get_clear_all_notifications_use_case(
    notification_repo: INotificationRepository = Depends(get_inapp_notification_repo),
    uow: IUnitOfWork = Depends(get_unit_of_work),
) -> ClearAllNotifications:
    return ClearAllNotifications(notification_repo=notification_repo, uow=uow)


def get_log_entries_use_case(
    log_repo: ILogRepository = Depends(get_log_repo),
) -> GetLogEntries:
    return GetLogEntries(log_repo=log_repo)
