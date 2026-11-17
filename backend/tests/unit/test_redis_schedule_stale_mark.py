"""
The stale mark of the Redis schedule coordinator: the first request after a
walk sets it, a later request keeps the earlier moment, and the walk takes
and clears it.
"""

from datetime import UTC
from datetime import datetime

from src.modules.fulfillment.adapters.outbound.external.schedule_recompute.redis_generation_counter import (
    RedisScheduleRecomputeGenerationCounter,
)


class _FakeRedis:
    def __init__(self) -> None:
        self.values: dict[str, str] = {}

    async def set(self, key: str, value: object, nx: bool = False) -> bool:
        if nx and key in self.values:
            return False
        self.values[key] = str(value)
        return True

    async def get(self, key: str) -> str | None:
        return self.values.get(key)

    async def getdel(self, key: str) -> str | None:
        return self.values.pop(key, None)


async def test_the_first_request_marks_the_schedule_stale_and_a_walk_clears_it() -> None:
    counter = RedisScheduleRecomputeGenerationCounter(_FakeRedis())  # type: ignore[arg-type]
    first = datetime(2026, 10, 25, 9, 0, tzinfo=UTC)

    await counter.mark_stale(first)
    await counter.mark_stale(datetime(2026, 10, 25, 9, 5, tzinfo=UTC))

    assert await counter.stale_since() == first
    assert await counter.take_stale_since() == first
    assert await counter.stale_since() is None
