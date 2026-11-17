"""
One delivery attempt of one event to one webhook subscription, the audit
trail admins use to debug failing receivers. Append-only.
"""

from dataclasses import dataclass
from datetime import datetime

from src.shared_kernel.domain.entities.base import Entity


@dataclass
class WebhookDelivery(Entity):
    subscription_id: int
    event_type: str
    source_event_id: str  # event bus message ID (dedup + retry tracking)
    payload: str  # the exact JSON body that was sent
    attempted_at: datetime
    http_status: int | None  # None when the request itself failed
    duration_ms: int | None
    error: str | None
    success: bool
