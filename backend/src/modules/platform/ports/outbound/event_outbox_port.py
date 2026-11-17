"""
The transactional outbox as seen by the relay worker.

Split from IEventBus deliberately: IEventBus is the *producer* side (a use
case staging an event inside its own transaction), this is the *relay* side
(draining staged rows onto the stream). Keeping the relay behind a port is
what lets it live in src/infrastructure without importing an adapter.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from typing import runtime_checkable


@dataclass(frozen=True)
class OutboxMessage:
    """One staged event, as the relay needs it."""

    id: int
    event_id: str
    event_type: str
    payload: str
    attempts: int


@runtime_checkable
class IEventOutbox(Protocol):
    async def try_lock(self) -> bool:
        """Claims the single relay slot for this tick.

        Production runs several processes, and only one of them may relay
        at a time, so a batch is published in id order without another
        relay interleaving with it. Returns False when another holds the
        lock, in which case the caller must do nothing this tick."""
        ...

    async def fetch_unpublished(self, limit: int) -> list[OutboxMessage]:
        """The oldest unpublished rows, in id order."""
        ...

    async def mark_published(self, ids: Sequence[int]) -> None: ...

    async def record_failure(self, message_id: int, error: str) -> int:
        """Increments the attempt counter and stores the error. Returns the
        new attempt count so the caller can log a stuck row."""
        ...

    async def purge_published(self, older_than: datetime) -> int:
        """Deletes relayed rows older than `older_than`; returns the count."""
        ...
