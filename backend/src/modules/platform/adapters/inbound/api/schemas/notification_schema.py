"""Re-exports notification domain transfer objects for the HTTP layer."""

from src.modules.platform.application.dto.notification_dto import NotificationResult
from src.modules.platform.application.dto.notification_dto import NotificationsResponse

__all__ = ["NotificationResult", "NotificationsResponse"]
