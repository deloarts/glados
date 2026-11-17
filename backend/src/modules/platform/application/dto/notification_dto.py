"""
DTOs for notification output results.
"""

from datetime import datetime

from src.modules.platform.application.dto.base import ResultBase
from src.modules.platform.application.dto.base import ResultModel


class NotificationResult(ResultBase):
    type: str
    title: str
    message: str
    is_read: bool
    created_at: datetime
    demand_item_id: int | None
    order_id: int | None
    project_id: int | None
    product_id: int | None
    meeting_id: int | None


class NotificationsResponse(ResultModel):
    total: int
    unread_count: int
    items: list[NotificationResult]
