"""Drains the transactional event outbox onto the Redis stream.

A supervisor loop that survives everything except cancellation, so the
component that prevents event loss cannot itself die quietly.

Delivery is at-least-once and that is on purpose. A crash between the XADD and
the `published_at` mark re-publishes the row on the next tick, producing a
second stream message with the SAME producer-assigned event_id, which is the
identity every consumer's idempotency guard keys on, so the duplicate message
does not become a duplicate notification, print job or webhook POST.

Ordering: one relay runs at a time, which the outbox's advisory lock
guarantees across the gunicorn processes, and within a batch it publishes
rows in id order. A failed XADD stops the batch rather than skipping past it,
so a batch never reorders itself. The order is not total, though. Ids are
assigned at insert and rows become visible at commit, so a transaction that
took a lower id but commits after the relay read a higher one is published
after it, and `admin republish-outbox` appends old events behind newer ones.
Consumers must therefore not rely on the order of events.
"""

import asyncio
import time
from collections.abc import Awaitable
from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from datetime import timedelta

import redis

from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.ports.outbound.event_outbox_port import IEventOutbox
from src.modules.platform.ports.outbound.event_outbox_port import OutboxMessage
from src.shared_kernel.domain.services.clock import now_utc

_BATCH_SIZE = 100  # rows relayed per tick
_IDLE_POLL_S = 1.0  # pause when there was nothing to relay
_ERROR_BACKOFF_S = 5.0  # pause after a Redis error or an unexpected exception
_PURGE_INTERVAL_S = 3600.0  # retention sweep, once an hour
_RETENTION_DAYS = 30  # published rows kept this long (the only full-payload record)
_STUCK_AFTER_ATTEMPTS = 10  # from here on, every further failure is an ERROR


class OutboxRelay:
    """Publishes staged outbox rows to the event stream, forever.

    `open_outbox` yields an IEventOutbox bound to a short-lived session; the
    session (and with it the advisory lock) is released at the end of every
    tick. `publish` performs the XADD and must RAISE on a transport failure;
    a swallowed error would mark rows published that never reached Redis.
    """

    def __init__(
        self,
        open_outbox: Callable[[], AbstractAsyncContextManager[IEventOutbox]],
        publish: Callable[[OutboxMessage], Awaitable[None]],
    ) -> None:
        self._open_outbox = open_outbox
        self._publish = publish
        self._last_purge = time.monotonic()

    async def run(self) -> None:
        try:
            while True:
                try:
                    relayed = await self._tick()
                    if relayed == 0:
                        await asyncio.sleep(_IDLE_POLL_S)
                except redis.RedisError:
                    # Rows are simply retried. No traceback, or an outage
                    # would fill the log with identical stacks.
                    log.warning(
                        "Outbox relay: Redis unavailable; retrying in %ss.", _ERROR_BACKOFF_S
                    )
                    await asyncio.sleep(_ERROR_BACKOFF_S)
                except Exception:
                    log.exception(
                        "Outbox relay: unexpected error; retrying in %ss.", _ERROR_BACKOFF_S
                    )
                    await asyncio.sleep(_ERROR_BACKOFF_S)
        except asyncio.CancelledError:
            log.info("Outbox relay stopped.")
            raise

    async def _tick(self) -> int:
        """One drain pass. Returns the number of rows relayed."""
        async with self._open_outbox() as outbox:
            if not await outbox.try_lock():
                return 0  # another process is relaying this tick

            messages = await outbox.fetch_unpublished(_BATCH_SIZE)
            if not messages:
                await self._maybe_purge(outbox)
                return 0

            published: list[int] = []
            failure: tuple[OutboxMessage, redis.RedisError] | None = None
            for message in messages:
                try:
                    await self._publish(message)
                except redis.RedisError as error:
                    failure = (message, error)
                    break  # stop the batch: skipping ahead would reorder the stream
                published.append(message.id)

            await outbox.mark_published(published)

            if failure is not None:
                failed_message, failed_error = failure
                attempts = await outbox.record_failure(failed_message.id, repr(failed_error))
                if attempts >= _STUCK_AFTER_ATTEMPTS:
                    # Rows are retried forever, so this marker is what makes a
                    # stuck one visible.
                    log.error(
                        "EVENT_OUTBOX_STUCK id=%s event_id=%s type=%s attempts=%d: %r",
                        failed_message.id,
                        failed_message.event_id,
                        failed_message.event_type,
                        attempts,
                        failed_error,
                    )
                raise failed_error

            await self._maybe_purge(outbox)
            return len(published)

    async def _maybe_purge(self, outbox: IEventOutbox) -> None:
        """Hourly retention sweep. Published rows stay 30 days as the only
        record of an event's full payload."""
        if time.monotonic() - self._last_purge < _PURGE_INTERVAL_S:
            return
        self._last_purge = time.monotonic()
        deleted = await outbox.purge_published(now_utc() - timedelta(days=_RETENTION_DAYS))
        if deleted:
            log.info("Outbox relay: purged %d published row(s) older than 30 days.", deleted)
