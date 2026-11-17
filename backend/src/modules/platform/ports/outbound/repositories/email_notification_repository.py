"""
Abstract interface for email notification persistence.
"""

from typing import Protocol
from typing import runtime_checkable

from src.modules.platform.domain.entities.email_notification import EmailNotification


@runtime_checkable
class IEmailNotificationRepository(Protocol):
    async def get_all(self) -> list[EmailNotification]: ...
    async def get_by_receiver_id(self, receiver_id: int) -> list[EmailNotification]: ...
    async def get_distinct_receiver_ids(self) -> list[int]: ...
    async def save(self, notification: EmailNotification) -> EmailNotification: ...
    async def delete_by_id(self, id: int) -> None: ...
