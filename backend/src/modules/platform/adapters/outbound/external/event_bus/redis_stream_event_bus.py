"""
The outbox relay's transport onto the glados:events Redis stream. Use cases
never publish here: they stage events through OutboxEventBus, and the relay
hands each committed row to `publish_raw`.

`publish_raw` raises on a Redis error, because its caller must leave the row
unpublished and retry rather than drop it. It does not trim the stream on
XADD; stream_trimmer.py does that, and only past entries every consumer group
is done with.
"""

from typing import Any

import redis.asyncio

from src.modules.platform.infrastructure.events.codec import EVENT_ID_FIELD
from src.modules.platform.infrastructure.events.registry import EVENTS_STREAM


class RedisStreamEventBus:
    def __init__(self, redis_client: redis.asyncio.Redis, stream: str = EVENTS_STREAM) -> None:
        self._redis = redis_client
        self._stream = stream

    async def publish_raw(self, *, event_id: str, event_type: str, payload: str) -> str:
        """XADDs already-serialized outbox fields and returns the message id.

        Field names mirror codec.serialize exactly, so the consumer worker
        decodes a relayed message with the same codec and reads the
        producer-assigned event_id from it.
        """
        fields: dict[Any, Any] = {
            "type": event_type,
            "payload": payload,
            EVENT_ID_FIELD: event_id,
        }
        message_id = await self._redis.xadd(self._stream, fields)
        return str(message_id)
