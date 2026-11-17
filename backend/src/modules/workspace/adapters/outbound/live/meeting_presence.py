"""
Publishes who edits which meeting card on the live channel, beside the row
signals of committed changes, so every open meeting page shows the editor.
"""

import dataclasses
import json

import redis

from src.modules.platform.infrastructure.events.registry import LIVE_CHANNEL
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.infrastructure.redis_client import get_async_redis_client
from src.modules.platform.ports.outbound.live_signal import LiveResource
from src.modules.platform.ports.outbound.live_signal import LiveSignal


class RedisMeetingPresence:
    """Implements IMeetingPresence."""

    async def announce(self, card_id: int, user_id: int, *, editing: bool) -> None:
        signal = LiveSignal(
            resource=LiveResource.MEETING_CARD_PRESENCE,
            id=card_id,
            action="updated" if editing else "deleted",
            actor_id=user_id,
        )
        try:
            await get_async_redis_client().publish(
                LIVE_CHANNEL, json.dumps([dataclasses.asdict(signal)])
            )
        except (redis.RedisError, OSError):
            log.warning("Meeting presence: failed to publish; dropping.")
