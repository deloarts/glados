"""
The Redis-backed replay guard, exercised against a stub client.

The integration suite fakes this port entirely so it needs no Redis, which
means the adapter's own behaviour, the atomic claim-once semantics and,
above all, the fail-open posture, is only covered here.

Fail-open is the part worth being careful about: an outage must degrade
replay protection, not block the TOTP verification it guards.
"""

import redis

from src.modules.platform.adapters.outbound.external.login_attempts.redis_replay_guard import (
    RedisReplayGuard,
)


class StubRedis:
    """Enough of redis.asyncio.Redis's SET NX EX for this adapter."""

    def __init__(self) -> None:
        self.values: dict[str, str] = {}
        self.set_calls: list[tuple[str, str, bool, int]] = []

    async def set(self, name: str, value: str, nx: bool = False, ex: int | None = None) -> bool:
        self.set_calls.append((name, value, nx, ex or 0))
        if nx and name in self.values:
            return False
        self.values[name] = value
        return True


class BrokenRedis:
    """Every call fails, as during an outage."""

    async def set(self, *args: object, **kwargs: object) -> bool:
        raise redis.ConnectionError("redis is down")


class TestClaimOnce:
    async def test_first_claim_succeeds(self):
        guard = RedisReplayGuard(StubRedis())

        assert await guard.consume_once("k", ttl_seconds=90) is True

    async def test_second_claim_of_the_same_key_fails(self):
        guard = RedisReplayGuard(StubRedis())

        assert await guard.consume_once("k", ttl_seconds=90) is True
        assert await guard.consume_once("k", ttl_seconds=90) is False

    async def test_claims_are_per_key(self):
        guard = RedisReplayGuard(StubRedis())

        assert await guard.consume_once("k1", ttl_seconds=90) is True
        assert await guard.consume_once("k2", ttl_seconds=90) is True

    async def test_uses_set_nx_ex_not_a_read_then_write(self):
        """The whole point is atomicity, a plain GET-then-SET would race
        two concurrent callers into both seeing "unclaimed"."""
        stub = StubRedis()
        guard = RedisReplayGuard(stub)

        await guard.consume_once("k", ttl_seconds=90)

        assert stub.set_calls == [("k", "1", True, 90)]


class TestFailsOpen:
    async def test_a_broken_client_still_returns_true(self):
        guard = RedisReplayGuard(BrokenRedis())  # type: ignore[arg-type]

        assert await guard.consume_once("k", ttl_seconds=90) is True
