"""
DTOs for outbound webhook subscriptions: what an admin sees when managing
subscriptions and the commands that create or update one.
"""

from datetime import datetime

from pydantic import BaseModel

from src.modules.platform.application.dto.base import ResultBase


class WebhookSubscriptionResult(ResultBase):
    """Subscription as shown in the admin UI, never includes the secret."""

    name: str
    url: str
    event_types: list[str]
    is_active: bool
    created: datetime
    creator_id: int


class CreatedWebhookSubscriptionResult(WebhookSubscriptionResult):
    """Returned exactly once, on creation, the only time the secret is visible."""

    secret: str


class CreateWebhookSubscriptionCommand(BaseModel):
    name: str
    url: str
    event_types: list[str]
    is_active: bool = True


class UpdateWebhookSubscriptionCommand(BaseModel):
    name: str
    url: str
    event_types: list[str]
    is_active: bool


class WebhookDeliveryResult(ResultBase):
    subscription_id: int
    event_type: str
    source_event_id: str
    payload: str
    attempted_at: datetime
    http_status: int | None
    duration_ms: int | None
    error: str | None
    success: bool


class WebhookDeliveriesResult(BaseModel):
    total: int
    items: list[WebhookDeliveryResult]
