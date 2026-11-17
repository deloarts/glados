"""
Redis-backed attempt counters and locks, the shared implementation of
ILoginAttemptTracker for login and any other feature needing the same
count/lock/expire shape, e.g. SendMail's per-user rate limit (see
domain/services/mail_policy.py). The Redis key prefixes below keep the
"login" spelling for compatibility with already-persisted lockout keys
(renaming them would silently drop every in-flight lockout on
deploy); non-login callers namespace themselves within that space by
prefixing their own `key` argument (e.g. `mail:{user_id}`), so a login
username and a mail scope can never collide.

Redis rather than Postgres because every value here is disposable and
self-expiring: counters and locks want a TTL, and putting a write on a hot
path into the primary database buys nothing.

**Falls back while Redis is down.** Every method catches `redis.RedisError`
and hands the call to the in-process `fallback` tracker, so the login
throttle and the other limits keep holding per worker instead of failing
open. Failing closed would turn a cache outage into a total authentication
(or mail-sending) outage, which is far worse than a limit that holds per
worker for a while. Without a fallback, as in the CLI, which only clears
keys, a method answers as if there were no failures on record. The gap is
logged loudly either way so it is visible.
"""

from __future__ import annotations

import redis
import redis.asyncio

from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.ports.outbound.login_attempt_tracker_port import ILoginAttemptTracker

_FAILURE_PREFIX = "glados:login:failures:"
_LOCK_PREFIX = "glados:login:lock:"

# Counters expire on their own so a single failure years ago never adds up
# with one today. Comfortably longer than any sane lockout window.
_FAILURE_TTL_SECONDS = 24 * 60 * 60

# Characters Redis' MATCH treats as glob syntax, escaped in release_prefix so
# a username containing one cannot widen the match.
_GLOB_CHARACTERS = "\\*?[]^"


def _glob_escape(text: str) -> str:
    return "".join(f"\\{c}" if c in _GLOB_CHARACTERS else c for c in text)


class RedisLoginAttemptTracker:
    def __init__(
        self, client: redis.asyncio.Redis, *, fallback: ILoginAttemptTracker | None = None
    ) -> None:
        self._redis = client
        self._fallback = fallback

    def _warn_outage(self, action: str, key: str) -> None:
        if self._fallback is not None:
            log.warning(
                "Redis unavailable; %s for %r handled by the in-process fallback, "
                "so the limit holds per worker while this persists.",
                action,
                key,
                exc_info=True,
            )
        else:
            log.warning(
                "Redis unavailable; %s for %r skipped, so the limit is not "
                "enforced while this persists.",
                action,
                key,
                exc_info=True,
            )

    async def record_failure(self, key: str) -> int:
        redis_key = f"{_FAILURE_PREFIX}{key}"
        try:
            count = int(await self._redis.incr(redis_key))
            await self._redis.expire(redis_key, _FAILURE_TTL_SECONDS)
            return count
        except redis.RedisError:
            self._warn_outage("failure count", key)
            if self._fallback is not None:
                return await self._fallback.record_failure(key)
            return 0

    async def reset(self, key: str) -> None:
        try:
            await self._redis.delete(f"{_FAILURE_PREFIX}{key}", f"{_LOCK_PREFIX}{key}")
        except redis.RedisError:
            self._warn_outage("reset", key)
        # Cleared in the fallback too, so failures recorded there during an
        # outage do not come back to lock someone who has since succeeded.
        if self._fallback is not None:
            await self._fallback.reset(key)

    async def lock(self, key: str, seconds: int) -> None:
        try:
            await self._redis.setex(f"{_LOCK_PREFIX}{key}", seconds, "1")
            await self._redis.delete(f"{_FAILURE_PREFIX}{key}")
            log.warning("%r locked for %s seconds after repeated failures.", key, seconds)
        except redis.RedisError:
            self._warn_outage("lock", key)
            if self._fallback is not None:
                await self._fallback.lock(key, seconds)

    async def lock_ttl(self, key: str) -> int:
        try:
            ttl = await self._redis.ttl(f"{_LOCK_PREFIX}{key}")
        except redis.RedisError:
            self._warn_outage("lock check", key)
            if self._fallback is not None:
                return await self._fallback.lock_ttl(key)
            return 0
        # -2 = no such key, -1 = key without expiry. Neither is a live lock
        # we should honour; -1 in particular would otherwise be permanent.
        return int(ttl) if isinstance(ttl, int) and ttl > 0 else 0

    async def claim(self, key: str, seconds: int) -> bool:
        """SET NX with an expiry, so concurrent workers cannot both claim.
        On a Redis outage the fallback decides, or without one the action is
        allowed."""
        try:
            return bool(await self._redis.set(f"{_LOCK_PREFIX}{key}", "1", ex=seconds, nx=True))
        except redis.RedisError:
            self._warn_outage("claim", key)
            if self._fallback is not None:
                return await self._fallback.claim(key, seconds)
            return True

    async def release_prefix(self, prefix: str) -> int:
        """Release every lock and counter whose key starts with `prefix`.
        Uses SCAN, never KEYS, for the reason clear_all gives."""
        removed = 0
        if self._fallback is not None:
            removed += await self._fallback.release_prefix(prefix)
        try:
            for redis_prefix in (_FAILURE_PREFIX, _LOCK_PREFIX):
                pattern = f"{_glob_escape(redis_prefix + prefix)}*"
                async for key in self._redis.scan_iter(match=pattern, count=500):
                    removed += int(await self._redis.delete(key))
        except redis.RedisError:
            log.warning("Redis unavailable; could not release %r.", prefix, exc_info=True)
        return removed

    async def clear_all(self) -> int:
        """Release every lock and counter, across every scope (login
        lockouts and mail rate limits alike, see the module docstring).

        Uses SCAN, never KEYS: KEYS blocks the whole server while it walks
        the keyspace, and this runs against the same Redis the event bus
        depends on.
        """
        removed = 0
        if self._fallback is not None:
            removed += await self._fallback.clear_all()
        try:
            for prefix in (_FAILURE_PREFIX, _LOCK_PREFIX):
                async for key in self._redis.scan_iter(match=f"{prefix}*", count=500):
                    removed += int(await self._redis.delete(key))
        except redis.RedisError:
            log.warning("Redis unavailable; could not clear lockouts/limits.", exc_info=True)
            return removed
        return removed
