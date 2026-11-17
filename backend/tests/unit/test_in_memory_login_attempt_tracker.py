"""
The in-process tracker RedisLoginAttemptTracker falls back to while Redis is
down, and the fallback itself: during an outage the limits keep holding
instead of failing open.
"""

import redis

from src.modules.platform.adapters.outbound.external.login_attempts import (
    in_memory_login_attempt_tracker as in_memory,
)
from src.modules.platform.adapters.outbound.external.login_attempts.in_memory_login_attempt_tracker import (
    InMemoryLoginAttemptTracker,
)
from src.modules.platform.adapters.outbound.external.login_attempts.redis_login_attempt_tracker import (
    RedisLoginAttemptTracker,
)


class FakeClock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


class BrokenRedis:
    """Every call fails, as during an outage."""

    def _boom(self, *args: object, **kwargs: object):
        raise redis.ConnectionError("redis is down")

    incr = expire = delete = setex = ttl = set = scan_iter = _boom


class TestInMemoryTracker:
    def setup_method(self):
        self.clock = FakeClock()
        self.original = in_memory.time.monotonic
        in_memory.time.monotonic = self.clock  # type: ignore[assignment]
        self.tracker = InMemoryLoginAttemptTracker()

    def teardown_method(self):
        in_memory.time.monotonic = self.original  # type: ignore[assignment]

    async def test_counts_failures_per_key(self):
        assert await self.tracker.record_failure("alice") == 1
        assert await self.tracker.record_failure("alice") == 2
        assert await self.tracker.record_failure("bob") == 1

    async def test_a_lock_expires_on_its_own(self):
        await self.tracker.lock("alice", 60)
        assert await self.tracker.lock_ttl("alice") == 60

        self.clock.now += 61

        assert await self.tracker.lock_ttl("alice") == 0

    async def test_locking_clears_the_counter(self):
        await self.tracker.record_failure("alice")
        await self.tracker.lock("alice", 60)

        assert await self.tracker.record_failure("alice") == 1

    async def test_counters_expire_after_a_day(self):
        await self.tracker.record_failure("alice")
        self.clock.now += 24 * 60 * 60 + 1

        assert await self.tracker.record_failure("alice") == 1

    async def test_claim_is_once_per_period(self):
        assert await self.tracker.claim("fetch:7", 5) is True
        assert await self.tracker.claim("fetch:7", 5) is False
        self.clock.now += 6
        assert await self.tracker.claim("fetch:7", 5) is True

    async def test_reset_release_prefix_and_clear_all(self):
        await self.tracker.lock("alice|1", 60)
        await self.tracker.lock("alice|2", 60)
        await self.tracker.lock("bob|1", 60)
        await self.tracker.record_failure("carol")

        assert await self.tracker.release_prefix("alice|") == 2
        assert await self.tracker.lock_ttl("bob|1") == 60
        await self.tracker.reset("bob|1")
        assert await self.tracker.lock_ttl("bob|1") == 0
        assert await self.tracker.clear_all() == 1


class TestRedisFallsBackToTheInProcessTracker:
    def setup_method(self):
        self.fallback = InMemoryLoginAttemptTracker()
        self.tracker = RedisLoginAttemptTracker(BrokenRedis(), fallback=self.fallback)  # type: ignore[arg-type]

    async def test_failures_keep_counting(self):
        assert await self.tracker.record_failure("alice") == 1
        assert await self.tracker.record_failure("alice") == 2

    async def test_a_lock_keeps_holding(self):
        """The point of the fallback: a Redis outage no longer turns the
        login throttle off."""
        await self.tracker.lock("alice", 900)

        assert await self.tracker.lock_ttl("alice") == 900

    async def test_reset_clears_the_fallback(self):
        await self.tracker.lock("alice", 900)
        await self.tracker.reset("alice")

        assert await self.tracker.lock_ttl("alice") == 0

    async def test_claim_is_decided_by_the_fallback(self):
        assert await self.tracker.claim("fetch:7", 5) is True
        assert await self.tracker.claim("fetch:7", 5) is False

    async def test_the_outage_is_logged(self, glados_caplog):
        await self.tracker.record_failure("alice")

        assert any("in-process fallback" in r.getMessage() for r in glados_caplog.records)
