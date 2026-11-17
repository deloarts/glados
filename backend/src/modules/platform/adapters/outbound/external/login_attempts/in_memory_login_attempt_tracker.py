"""
In-process ILoginAttemptTracker, the fallback RedisLoginAttemptTracker turns
to while Redis is unavailable, so the login throttle, the mail rate limit
and the other attempt limits keep holding instead of failing open.

Every worker process keeps its own counters, so during an outage a limit
holds per worker rather than across all of them, and whatever the store
recorded is forgotten once Redis answers again. Both are acceptable for a
degraded mode: an attacker gets at most the number of workers times the
usual budget, and nobody is locked out by a lock that cannot be read.

One instance must live for the whole lifetime of a worker process (see
get_login_attempt_tracker in deps/services.py), or its counters would never add up.
Counters and locks expire on the monotonic clock, as their Redis keys do.
"""

import threading
import time

# The same lifetime as the Redis counters, see redis_login_attempt_tracker.py.
_FAILURE_TTL_SECONDS = 24 * 60 * 60
# Expired entries are swept on every this many writes, so the maps cannot
# grow without bound under a stream of new keys.
_PRUNE_EVERY = 1000


class InMemoryLoginAttemptTracker:
    def __init__(self) -> None:
        # key -> (count, expires at); key -> expires at
        self._failures: dict[str, tuple[int, float]] = {}
        self._locks: dict[str, float] = {}
        self._mutex = threading.Lock()
        self._writes = 0

    async def record_failure(self, key: str) -> int:
        now = time.monotonic()
        with self._mutex:
            self._maybe_prune(now)
            count, expires_at = self._failures.get(key, (0, now))
            if expires_at <= now:
                count = 0
            count += 1
            self._failures[key] = (count, now + _FAILURE_TTL_SECONDS)
            return count

    async def reset(self, key: str) -> None:
        with self._mutex:
            self._failures.pop(key, None)
            self._locks.pop(key, None)

    async def lock(self, key: str, seconds: int) -> None:
        now = time.monotonic()
        with self._mutex:
            self._maybe_prune(now)
            self._locks[key] = now + seconds
            self._failures.pop(key, None)

    async def lock_ttl(self, key: str) -> int:
        now = time.monotonic()
        with self._mutex:
            expires_at = self._locks.get(key)
            if expires_at is None or expires_at <= now:
                return 0
            # Rounded up, so a lock with a fraction of a second left still
            # reports itself as live.
            return max(int(expires_at - now + 0.999), 1)

    async def claim(self, key: str, seconds: int) -> bool:
        now = time.monotonic()
        with self._mutex:
            self._maybe_prune(now)
            expires_at = self._locks.get(key)
            if expires_at is not None and expires_at > now:
                return False
            self._locks[key] = now + seconds
            return True

    async def release_prefix(self, prefix: str) -> int:
        with self._mutex:
            keys = [k for k in self._failures if k.startswith(prefix)]
            keys += [k for k in self._locks if k.startswith(prefix)]
            for key in keys:
                self._failures.pop(key, None)
                self._locks.pop(key, None)
            return len(keys)

    async def clear_all(self) -> int:
        with self._mutex:
            removed = len(self._failures) + len(self._locks)
            self._failures.clear()
            self._locks.clear()
            return removed

    def _maybe_prune(self, now: float) -> None:
        """Drops expired entries every _PRUNE_EVERY writes. Called with the
        mutex held."""
        self._writes += 1
        if self._writes % _PRUNE_EVERY:
            return
        self._failures = {k: v for k, v in self._failures.items() if v[1] > now}
        self._locks = {k: v for k, v in self._locks.items() if v > now}
