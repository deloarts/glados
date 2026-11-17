"""
Redis-backed IReplayGuard. `SET key value NX EX ttl` is an atomic
"claim this key once" primitive, the first caller for a given key within
ttl_seconds gets the write (and True back), every later caller gets
neither (False), with no read-then-write race between concurrent callers.

**Fails open**: a Redis outage must degrade replay protection, not block
every TOTP verification. The gap is logged loudly so it is visible.
"""

import redis
import redis.asyncio

from src.modules.platform.infrastructure.logging.logger import log


class RedisReplayGuard:
    def __init__(self, client: redis.asyncio.Redis) -> None:
        self._redis = client

    async def consume_once(self, key: str, ttl_seconds: int) -> bool:
        try:
            return bool(await self._redis.set(key, "1", nx=True, ex=ttl_seconds))
        except redis.RedisError:
            log.warning("Redis unavailable; replay guard not enforced for %r.", key, exc_info=True)
            return True
