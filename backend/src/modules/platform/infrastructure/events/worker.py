"""Async consumer loop for one Redis Streams consumer group.

Runs as a lifespan background task. Reads batches from the events stream,
decodes them, and awaits the group's async handler for each event. A
message is acknowledged only after the handler returns, so a crash
mid-handling leaves it pending and the periodic
reclaim scan redelivers it. A message that keeps failing is moved to the
dead-letter stream after _MAX_DELIVERIES attempts (copied there first, then
acknowledged, so it is never lost on the way); undecodable messages are
dropped immediately.

Failure policy: no single exception may permanently kill a consumer group.
`run()` is a supervisor loop around one consumer *session*: any exception
that escapes the session (a malformed reply shape, a decode-path bug, a
failing XGROUP CREATE) is logged with its traceback and the session is
restarted after a flat backoff. Only `asyncio.CancelledError` (a
BaseException, so no `except Exception` arm can swallow it) ends the loop,
which is how lifespan shutdown stops the worker. A group that Redis lost
(NOGROUP) is created again at the end of the stream, where a fresh group
starts too, so a Redis that comes back empty needs no process restart.
"""

import asyncio
import os
import socket
import time
from collections.abc import Awaitable
from collections.abc import Callable
from typing import Any
from typing import cast

import redis
import redis.asyncio
from prometheus_client import Counter

from src.modules.platform.infrastructure.events.codec import EVENT_ID_FIELD
from src.modules.platform.infrastructure.events.codec import EventCodecError
from src.modules.platform.infrastructure.events.codec import deserialize
from src.modules.platform.infrastructure.events.registry import DEAD_LETTER_STREAM
from src.modules.platform.infrastructure.events.registry import EVENTS_STREAM
from src.modules.platform.infrastructure.logging.logger import log
from src.shared_kernel.domain.events.base import DomainEvent
from src.shared_kernel.domain.services.clock import now_utc

_READ_COUNT = 10  # messages per XREADGROUP call
_BLOCK_MS = 1_000  # XREADGROUP block timeout when waiting for new messages
_RECLAIM_INTERVAL_S = 60.0  # how often to scan the pending list
_MIN_IDLE_MS = 60_000  # pending age before a message is redelivered the first time
_MAX_IDLE_MS = 900_000  # 15 min, cap of the exponential redelivery backoff
_MAX_DELIVERIES = 5  # dead-letter a message after this many attempts
_ERROR_BACKOFF_S = 5.0  # pause after a Redis connection error
_DEAD_LETTER_MAXLEN = 10_000  # approximate cap of the dead-letter stream

# The shared client decodes responses, so stream ids and fields arrive as str,
# while redis-py annotates its stream replies for both decoded and raw clients.
_StreamEntry = tuple[str, dict[str, str]]
_StreamReply = list[tuple[str, list[_StreamEntry]]]

EVENTS_DEAD_LETTERED = Counter(
    "glados_events_dead_lettered_total",
    "Events a consumer group gave up on and moved to the dead-letter stream.",
    ["group"],
)


def _default_consumer_name(group: str) -> str:
    """One consumer per OS process, named by hostname and pid; a shared
    name would make every worker read the same pending list. Dead consumers
    left by restarts hold no entries and are accepted.
    """
    return f"{group}-{socket.gethostname()}-{os.getpid()}"


class EventWorker:
    """One consumer group draining the event stream."""

    def __init__(
        self,
        redis_client: redis.asyncio.Redis,
        group: str,
        handler: Callable[[DomainEvent, str], Awaitable[None]],
        stream: str = EVENTS_STREAM,
        consumer: str | None = None,
    ) -> None:
        """`handler(event, source_event_id)` is awaited; raising retries the
        message. `consumer` defaults to a per-process identity."""
        self._redis = redis_client
        self._group = group
        self._consumer = consumer or _default_consumer_name(group)
        self._handler = handler
        self._stream = stream

    async def run(self) -> None:
        """Keeps one consumer session alive forever. Redis errors retry
        inside the session; anything else rebuilds it after a backoff, which
        keeps a persistently failing read from spinning the CPU.
        """
        try:
            while True:
                try:
                    await self._run_session()
                except Exception:
                    log.exception(
                        "Event worker %r: unexpected error; restarting in %ss.",
                        self._group,
                        _ERROR_BACKOFF_S,
                    )
                    await asyncio.sleep(_ERROR_BACKOFF_S)
        except asyncio.CancelledError:
            log.info("Event worker %r stopped.", self._group)
            raise

    async def _run_session(self) -> None:
        await self._ensure_group()
        log.info(
            "Event worker %r started on stream %r as %r.",
            self._group,
            self._stream,
            self._consumer,
        )

        # A dead process's pending entries sit under its old consumer name,
        # so reclaim from the whole group right away.
        await self._reclaim_stale()

        read_id = "0"
        last_reclaim = time.monotonic()

        while True:
            try:
                if time.monotonic() - last_reclaim >= _RECLAIM_INTERVAL_S:
                    await self._reclaim_stale()
                    last_reclaim = time.monotonic()

                response = cast(
                    _StreamReply,
                    await self._redis.xreadgroup(
                        self._group,
                        self._consumer,
                        {self._stream: read_id},
                        count=_READ_COUNT,
                        block=_BLOCK_MS if read_id == ">" else None,
                    ),
                )
                messages = response[0][1] if response else []

                if read_id != ">":
                    if not messages:
                        read_id = ">"
                        continue
                    # Advance past this batch so messages left pending by a
                    # failing handler wait for the reclaim scan instead of
                    # being re-read in a hot loop.
                    read_id = messages[-1][0]

                for message_id, fields in messages:
                    await self._process(message_id, fields)
            except redis.ResponseError as error:
                if "NOGROUP" not in str(error):
                    log.exception(
                        "Event worker %r: Redis error; retrying in %ss.",
                        self._group,
                        _ERROR_BACKOFF_S,
                    )
                    await asyncio.sleep(_ERROR_BACKOFF_S)
                    continue
                # Redis lost the stream or the group, after a restart without
                # its data or a flush. The group is created again at the
                # stream's end, so events relayed in between are not seen
                # until `admin republish-outbox` puts them back.
                log.error(
                    "Event worker %r: the consumer group is gone from Redis; "
                    "creating it again at the end of the stream.",
                    self._group,
                )
                await self._ensure_group()
                read_id = "0"
            except redis.RedisError:
                log.exception(
                    "Event worker %r: Redis error; retrying in %ss.",
                    self._group,
                    _ERROR_BACKOFF_S,
                )
                await asyncio.sleep(_ERROR_BACKOFF_S)

    async def _ensure_group(self) -> None:
        try:
            await self._redis.xgroup_create(self._stream, self._group, id="$", mkstream=True)
        except redis.ResponseError as e:
            if "BUSYGROUP" not in str(e):
                raise

    async def _process(self, message_id: str, fields: dict[str, str]) -> None:
        try:
            event = deserialize(fields)
        except EventCodecError:
            log.exception(
                "Event worker %r: dropping undecodable message %s: %r.",
                self._group,
                message_id,
                fields,
            )
            await self._redis.xack(self._stream, self._group, message_id)
            return

        # The producer's event_id survives a relay re-publish, unlike the
        # message id, which remains the fallback.
        source_event_id = fields.get(EVENT_ID_FIELD) or message_id

        try:
            await self._handler(event, source_event_id)
        except Exception:
            log.exception(
                "Event worker %r: handler failed for message %s (%s); will retry.",
                self._group,
                message_id,
                fields.get("type"),
            )
            return  # no ack, stays pending until the reclaim scan redelivers it

        await self._redis.xack(self._stream, self._group, message_id)

    async def _reclaim_stale(self) -> None:
        """Redelivers stuck messages with exponential backoff per message,
        capped at _MAX_IDLE_MS, using the counters Redis keeps per entry. A
        missing idle time counts as old enough rather than wedging the queue.
        """
        pending = cast(
            list[dict[str, Any]],
            await self._redis.xpending_range(
                self._stream, self._group, min="-", max="+", count=_READ_COUNT, idle=_MIN_IDLE_MS
            ),
        )
        for entry in pending:
            message_id = entry["message_id"]
            times_delivered = int(entry["times_delivered"])

            if times_delivered >= _MAX_DELIVERIES:
                await self._dead_letter(message_id, times_delivered)
                continue

            required_idle_ms = min(_MIN_IDLE_MS * 2 ** (times_delivered - 1), _MAX_IDLE_MS)
            idle_ms = entry.get("time_since_delivered")
            if idle_ms is not None and int(idle_ms) < required_idle_ms:
                continue  # still inside this attempt's backoff window

            claimed = cast(
                list[_StreamEntry],
                await self._redis.xclaim(
                    self._stream, self._group, self._consumer, _MIN_IDLE_MS, [message_id]
                ),
            )
            for claimed_id, fields in claimed:
                await self._process(claimed_id, fields)

    async def _dead_letter(self, message_id: str, times_delivered: int) -> None:
        """Copies an exhausted message to the dead-letter stream and acks it
        only afterwards, so a failed copy is retried. The payload is never
        logged, since it can carry business data."""
        fields = await self._read_fields(message_id)
        event_type = fields.get("type") if fields else None
        entry: dict[Any, Any] = {
            **(fields or {}),
            "dead_group": self._group,
            "dead_source_id": message_id,
            "dead_deliveries": str(times_delivered),
            "dead_at": now_utc().isoformat(),
        }
        try:
            await self._redis.xadd(
                DEAD_LETTER_STREAM,
                entry,
                maxlen=_DEAD_LETTER_MAXLEN,
                approximate=True,
            )
        except redis.RedisError:
            log.exception(
                "Event worker %r: could not dead-letter message %s (%s); it stays pending.",
                self._group,
                message_id,
                event_type,
            )
            return
        log.error(
            "Event worker %r: dead-lettered message %s (%s) after %d failed deliveries.",
            self._group,
            message_id,
            event_type,
            times_delivered,
        )
        EVENTS_DEAD_LETTERED.labels(group=self._group).inc()
        await self._redis.xack(self._stream, self._group, message_id)

    async def _read_fields(self, message_id: str) -> dict[str, str] | None:
        """A message's fields, or None when it was trimmed."""
        try:
            entries = cast(
                list[_StreamEntry],
                await self._redis.xrange(self._stream, min=message_id, max=message_id, count=1),
            )
        except redis.RedisError:
            return None
        for _entry_id, fields in entries:
            return dict(fields)
        return None
