"""
Registry of every domain event that may travel through the event bus, keyed
by class name (the `type` field on stream messages), and the names of the
streams and channels the bus uses. Publishing or consuming an unregistered
type is a codec error: a new event is registered by its module in
src/bootstrap/registrations.py.
"""

from src.shared_kernel.domain.events.base import DomainEvent

EVENTS_STREAM = "glados:events"

# Where a consumer group puts a message it gave up on after its retry
# budget, so the event is kept for inspection and replay instead of only
# being logged (see EventWorker._reclaim_stale).
DEAD_LETTER_STREAM = "glados:events:dead"

# Pub/Sub channel for live row-sync signals (src/adapters/outbound/persistence/
# change_tracking.py). Separate from the stream above by design: it's an
# ephemeral broadcast to every connected app process, not a durable,
# load-balanced consumer group.
LIVE_CHANNEL = "glados:live"

# Every event type that may travel through the bus, keyed by class name (the
# `type` field on stream messages). Each module registers its events at
# startup through src/bootstrap/registrations.py.
EVENT_REGISTRY: dict[str, type[DomainEvent]] = {}


def register_events(*classes: type[DomainEvent]) -> None:
    """Adds event classes to EVENT_REGISTRY. Registering a class again is
    harmless; another class under a name already taken is an error, since
    the stream could not tell the two apart."""
    for cls in classes:
        known = EVENT_REGISTRY.setdefault(cls.__name__, cls)
        if known is not cls:
            raise ValueError(f"Two event classes are named {cls.__name__}: {known} and {cls}.")
