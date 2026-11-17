"""Converts between Notification domain entity and DTOs."""

from src.modules.platform.application.dto.notification_dto import NotificationResult
from src.modules.platform.domain.entities.notification import Notification


class NotificationMapper:
    @staticmethod
    def to_result(notification: Notification) -> NotificationResult:
        return NotificationResult(
            id=notification.id,
            public_id=notification.public_id,
            type=notification.type.value,
            title=notification.title,
            message=notification.message,
            is_read=notification.is_read,
            created_at=notification.created_at,
            demand_item_id=notification.demand_item_id,
            order_id=notification.order_id,
            project_id=notification.project_id,
            product_id=notification.product_id,
            meeting_id=notification.meeting_id,
        )
