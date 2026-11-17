"""
Domain events of quote requests (RFQs). The status changes come from the
lifecycle reconciler, which derives the status from the request's intents
and line states, among them whether the order lines its awards created are
still live.
"""

from dataclasses import dataclass

from src.modules.fulfillment.domain.value_objects.quote_request_status import QuoteRequestStatus
from src.shared_kernel.domain.events.base import DomainEvent


@dataclass(frozen=True)
class QuoteRequestStatusChanged(DomainEvent):
    """A quote request's derived status changed. `actor_id` is the user
    whose action led to the change."""

    quote_request_id: int
    request_number: str
    creator_id: int
    old_status: QuoteRequestStatus
    new_status: QuoteRequestStatus
    actor_id: int
