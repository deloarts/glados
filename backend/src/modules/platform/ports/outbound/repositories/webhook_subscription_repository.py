"""Repository protocol for managing webhook subscriptions.

Supports fetching all subscriptions (active and inactive) and full CRUD
operations.
"""

from typing import Protocol
from typing import runtime_checkable

from src.modules.platform.domain.entities.webhook_subscription import WebhookSubscription


@runtime_checkable
class IWebhookSubscriptionRepository(Protocol):
    async def get_all(self) -> list[WebhookSubscription]: ...
    async def get_active(self) -> list[WebhookSubscription]: ...
    async def get_by_id(self, subscription_id: int) -> WebhookSubscription | None: ...
    async def save(self, subscription: WebhookSubscription) -> WebhookSubscription: ...
    async def delete(self, subscription_id: int) -> None: ...
