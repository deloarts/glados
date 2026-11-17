"""HTTP schemas for webhook subscription operations: creation, management, and delivery
tracking."""

from pydantic import BaseModel

from src.modules.platform.application.dto.webhook_dto import CreatedWebhookSubscriptionResult
from src.modules.platform.application.dto.webhook_dto import WebhookDeliveriesResult
from src.modules.platform.application.dto.webhook_dto import WebhookDeliveryResult
from src.modules.platform.application.dto.webhook_dto import WebhookSubscriptionResult

__all__ = [
    "CreatedWebhookSubscriptionResult",
    "WebhookDeliveriesResult",
    "WebhookDeliveryResult",
    "WebhookSubscriptionCreateRequest",
    "WebhookSubscriptionResult",
    "WebhookSubscriptionUpdateRequest",
]


class WebhookSubscriptionCreateRequest(BaseModel):
    name: str
    url: str
    event_types: list[str]
    is_active: bool = True


class WebhookSubscriptionUpdateRequest(BaseModel):
    name: str
    url: str
    event_types: list[str]
    is_active: bool
