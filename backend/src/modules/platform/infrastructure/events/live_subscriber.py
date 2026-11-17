"""
Redis Pub/Sub subscriber for the live row-sync channel (glados:live).
Runs as a lifespan background task, one per app process, unlike EventWorker
(a Streams consumer group, which load-balances one message to one process),
Pub/Sub broadcasts every message to every subscriber, which is exactly what
live sync needs: each of the N gunicorn workers holds a disjoint set of SSE
connections, so every process must see every signal to reach its own clients.

No ack, no reclaim, no consumer group, Pub/Sub has none of that machinery,
and none of it is missed: a signal that arrives while disconnected is not
redelivered, which is fine, because the client's reconnect path does a full
refresh anyway (see LiveHub / the live SSE endpoint).
"""

import asyncio
import json
from collections.abc import Callable

import redis
import redis.asyncio

from src.modules.platform.infrastructure.events.registry import LIVE_CHANNEL
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.ports.outbound.live_signal import LiveSignal

_GET_MESSAGE_TIMEOUT_S = 1.0
_ERROR_BACKOFF_S = 5.0


class LiveEventSubscriber:
    """Subscribes to `channel` and hands each decoded batch of signals to
    `handler`, a plain sync callable run inline on the event loop: it only
    does dict lookups and Queue.put_nowait (see LiveHub.broadcast), and
    asyncio.Queue is not thread-safe, so it must never move to a worker
    thread."""

    def __init__(
        self,
        redis_client: redis.asyncio.Redis,
        handler: Callable[[list[LiveSignal]], None],
        channel: str = LIVE_CHANNEL,
    ) -> None:
        self._redis = redis_client
        self._handler = handler
        self._channel = channel

    async def run(self) -> None:
        try:
            while True:
                try:
                    await self._listen()
                except redis.RedisError:
                    log.warning("Live subscriber: Redis error; retrying in %ss.", _ERROR_BACKOFF_S)
                    await asyncio.sleep(_ERROR_BACKOFF_S)
        except asyncio.CancelledError:
            log.info("Live subscriber stopped.")
            raise

    async def _listen(self) -> None:
        async with self._redis.pubsub() as pubsub:
            await pubsub.subscribe(self._channel)
            log.info("Live subscriber: listening on %r.", self._channel)
            while True:
                message = await pubsub.get_message(
                    ignore_subscribe_messages=True, timeout=_GET_MESSAGE_TIMEOUT_S
                )
                if message is None:
                    continue
                self._process(message["data"])

    def _process(self, data: str) -> None:
        try:
            signals = [LiveSignal(**fields) for fields in json.loads(data)]
        except (TypeError, ValueError, KeyError):
            log.debug("Live subscriber: dropping undecodable message: %r.", data)
            return

        try:
            self._handler(signals)
        except Exception:
            log.exception("Live subscriber: handler failed for %d signal(s).", len(signals))
