"""
An outbound webhook endpoint registered by an admin. Each subscription names
the event types it wants (or ["*"] for all) and carries an HMAC secret used
to sign every delivery. The secret is shown once on creation, never again.
"""

from dataclasses import dataclass
from datetime import datetime

from src.shared_kernel.domain.entities.base import Entity


@dataclass
class WebhookSubscription(Entity):
    name: str
    url: str
    secret: str  # Standard Webhooks signing secret (whsec_ and base64), see the dispatcher
    event_types: list[str]  # event class names, or ["*"] for all events
    is_active: bool
    created: datetime
    creator_id: int

    def matches(self, event_type: str) -> bool:
        return "*" in self.event_types or event_type in self.event_types
