"""
The Redis-backed tracker, exercised against a stub client.

The integration suite fakes this port entirely so it needs no Redis, which
means the adapter's own behaviour, key naming, TTL handling, SCAN rather
than KEYS, and above all the fail-open posture, is only covered here.

Fail-open is the part worth being careful about: every method must answer
"nothing on record" when Redis is down. Failing closed would turn a cache
outage into a total authentication outage.
"""

import pytest
import redis

from src.modules.platform.adapters.outbound.external.login_attempts.redis_login_attempt_tracker import (
    RedisLoginAttemptTracker,
)


class StubRedis:
    """Enough of redis.asyncio.Redis for this adapter."""

    def __init__(self) -> None:
        self.values: dict[str, int] = {}
        self.ttls: dict[str, int] = {}
        self.expire_calls: list[tuple[str, int]] = []
        self.scan_calls = 0

    async def incr(self, key: str) -> int:
        self.values[key] = self.values.get(key, 0) + 1
        return self.values[key]

    async def expire(self, key: str, seconds: int) -> None:
        self.expire_calls.append((key, seconds))

    async def delete(self, *keys: str) -> int:
        removed = 0
        for key in keys:
            removed += 1 if self.values.pop(key, None) is not None else 0
            removed += 1 if self.ttls.pop(key, None) is not None else 0
        return removed

    async def setex(self, key: str, seconds: int, value: str) -> None:
        self.ttls[key] = seconds

    async def ttl(self, key: str) -> int:
        return self.ttls.get(key, -2)  # -2 = no such key

    async def scan_iter(self, match: str, count: int = 500):
        self.scan_calls += 1
        prefix = match.rstrip("*")
        for k in [k for k in {**self.values, **self.ttls} if k.startswith(prefix)]:
            yield k


class BrokenRedis:
    """Every call fails, as during an outage."""

    def _boom(self, *args: object, **kwargs: object):
        raise redis.ConnectionError("redis is down")

    incr = expire = delete = setex = ttl = scan_iter = _boom


@pytest.fixture
def stub():
    return StubRedis()


@pytest.fixture
def tracker(stub):
    return RedisLoginAttemptTracker(stub)


class TestCounting:
    async def test_record_failure_increments(self, tracker):
        assert await tracker.record_failure("alice") == 1
        assert await tracker.record_failure("alice") == 2

    async def test_counts_are_per_username(self, tracker):
        await tracker.record_failure("alice")

        assert await tracker.record_failure("bob") == 1

    async def test_counters_are_given_a_ttl(self, stub, tracker):
        """Otherwise one failure a year ago adds to one today."""
        await tracker.record_failure("alice")

        assert stub.expire_calls
        assert stub.expire_calls[0][1] > 0

    async def test_reset_forgets_failures(self, tracker):
        await tracker.record_failure("alice")
        await tracker.reset("alice")

        assert await tracker.record_failure("alice") == 1


class TestLocking:
    async def test_lock_sets_a_ttl(self, tracker):
        await tracker.lock("alice", 900)

        assert await tracker.lock_ttl("alice") == 900

    async def test_unlocked_accounts_report_zero(self, tracker):
        assert await tracker.lock_ttl("nobody") == 0

    async def test_locking_clears_the_counter(self, tracker):
        await tracker.record_failure("alice")
        await tracker.lock("alice", 900)

        assert await tracker.record_failure("alice") == 1

    async def test_reset_releases_a_lock(self, tracker):
        await tracker.lock("alice", 900)
        await tracker.reset("alice")

        assert await tracker.lock_ttl("alice") == 0

    async def test_a_key_without_expiry_is_not_treated_as_locked(self, stub, tracker):
        """TTL -1 means "no expiry set". Honouring it would lock the
        account permanently, with no way out but the CLI."""
        stub.ttls["glados:login:lock:alice"] = -1

        assert await tracker.lock_ttl("alice") == 0


class TestClearAll:
    async def test_removes_locks_and_counters(self, tracker):
        await tracker.record_failure("alice")
        await tracker.lock("bob", 900)

        removed = await tracker.clear_all()

        assert removed >= 1
        assert await tracker.lock_ttl("bob") == 0

    async def test_uses_scan_not_keys(self, stub, tracker):
        """KEYS blocks the whole server, and this shares Redis with the
        event bus."""
        await tracker.clear_all()

        assert stub.scan_calls > 0
        assert not hasattr(stub, "keys_called")


class TestFailsOpenWhenRedisIsDown:
    @pytest.fixture
    def broken(self):
        return RedisLoginAttemptTracker(BrokenRedis())

    async def test_record_failure_returns_zero(self, broken):
        assert await broken.record_failure("alice") == 0

    async def test_lock_ttl_reports_unlocked(self, broken):
        """The decisive one: a live lock that cannot be read must not
        block the login, or a Redis blip becomes an auth outage."""
        assert await broken.lock_ttl("alice") == 0

    async def test_reset_does_not_raise(self, broken):
        await broken.reset("alice")

    async def test_lock_does_not_raise(self, broken):
        await broken.lock("alice", 900)

    async def test_clear_all_does_not_raise(self, broken):
        assert await broken.clear_all() == 0

    async def test_a_zero_count_never_triggers_a_lockout(self, broken):
        """record_failure returning 0 keeps lockout_triggered false for any
        positive threshold, so the outage degrades to 'no enforcement'
        rather than 'lock everyone out'."""
        from src.modules.platform.domain.services.login_policy import lockout_triggered

        assert lockout_triggered(await broken.record_failure("alice"), 3) is False
