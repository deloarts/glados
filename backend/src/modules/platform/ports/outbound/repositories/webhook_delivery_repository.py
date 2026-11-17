"""Repository protocol for persisting and querying webhook delivery attempts.

Methods support paginated access to delivery history, deduplication of
already-delivered events, and filtering failed deliveries across all
subscriptions.
"""

from dataclasses import dataclass
from datetime import date
from datetime import datetime
from typing import Protocol
from typing import runtime_checkable

from src.modules.platform.domain.entities.webhook_delivery import WebhookDelivery


@dataclass
class WebhookDeliveryFilterDto:
    """Row filters for one subscription's delivery log. Empty fields do not
    filter."""

    success: bool | None = None
    event_type: str | None = None  # exact event type name
    attempted_from: date | None = None  # inclusive calendar day
    attempted_to: date | None = None  # inclusive calendar day


@runtime_checkable
class IWebhookDeliveryRepository(Protocol):
    async def save(self, delivery: WebhookDelivery) -> WebhookDelivery: ...
    async def get_by_id(self, delivery_id: int) -> WebhookDelivery | None: ...

    async def get_by_subscription_id(
        self,
        subscription_id: int,
        skip: int = 0,
        limit: int = 50,
        filters: WebhookDeliveryFilterDto | None = None,
    ) -> tuple[int, list[WebhookDelivery]]:
        """Returns (total, page) ordered newest first, narrowed by
        `filters` when given."""
        ...

    async def get_failed(self, skip: int = 0, limit: int = 50) -> tuple[int, list[WebhookDelivery]]:
        """Failed attempts across ALL subscriptions, newest first.

        The per-subscription view above is useless for the question an
        operator actually asks after an outage ("what did we fail to
        deliver?"), which is not scoped to one subscription and is never
        about the successes."""
        ...

    async def exists_success(self, subscription_id: int, source_event_id: str) -> bool:
        """True when this event was already delivered successfully to this
        subscription, used to skip subscribers on event redelivery."""
        ...

    async def recent_outcomes(
        self, subscription_id: int, limit: int
    ) -> list[tuple[datetime, bool]]:
        """(attempted_at, success) of this subscription's newest `limit`
        attempts, newest first. Feeds the dispatch circuit breaker, which
        needs only these two columns and never the payload."""
        ...
