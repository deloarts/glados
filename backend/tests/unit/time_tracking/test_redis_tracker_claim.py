"""
RedisLoginAttemptTracker.claim, the atomic "at most once per period" lock
behind the time tracking fetch cooldown: SET NX with an expiry under the
lock prefix, so lock_ttl and clear_all see it, and fail-open on a Redis
outage like every other method of the tracker.
"""

import redis

from src.modules.platform.adapters.outbound.external.login_attempts.redis_login_attempt_tracker import (
    RedisLoginAttemptTracker,
)


class StubRedis:
    def __init__(self, fail: bool = False) -> None:
        self.fail = fail
        self.values: dict[str, str] = {}
        self.calls: list[tuple[str, int | None, bool]] = []

    async def set(
        self, key: str, value: str, ex: int | None = None, nx: bool = False
    ) -> bool | None:
        if self.fail:
            raise redis.ConnectionError("down")
        self.calls.append((key, ex, nx))
        if nx and key in self.values:
            return None
        self.values[key] = value
        return True


async def test_claim_takes_the_lock_once() -> None:
    stub = StubRedis()
    tracker = RedisLoginAttemptTracker(stub)  # type: ignore[arg-type]

    assert await tracker.claim("time-tracking-month:7", 5)
    assert not await tracker.claim("time-tracking-month:7", 5)
    assert await tracker.claim("time-tracking-year:7", 5)
    assert stub.calls[0] == ("glados:login:lock:time-tracking-month:7", 5, True)


async def test_claim_fails_open_when_redis_is_down(glados_caplog) -> None:
    tracker = RedisLoginAttemptTracker(StubRedis(fail=True))  # type: ignore[arg-type]

    assert await tracker.claim("time-tracking-month:7", 5)
    assert any("not enforced" in r.getMessage() for r in glados_caplog.records)
