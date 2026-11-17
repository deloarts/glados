"""
Redis-backed IScheduleRecomputeGenerationCounter: two integer keys, `gen`
(incremented by every RecomputeMachineSchedule.execute_all() call right
before it decides whether to actually walk) and `processed` (the
generation the most recently completed walk covered). See that module's
docstring for the coalescing design these back.

No TTL on either key, deliberately: unlike RedisLoginAttemptTracker/
RedisReplayGuard, this counter's whole job is comparing "the generation I
minted" against "the generation the last walk covered" across however long
the process lives; an expiring key would silently reset that comparison's
baseline out from under it. Losing this state entirely (a restart, a
flush) is harmless by construction instead: the next execute_all() call
just starts counting from 0 again, and the worst case is one redundant
walk, never a wrongly-skipped one (see recompute_machine_schedule.py).

No fail-open handling here, unlike the other Redis adapters in this
codebase (RedisLoginAttemptTracker, RedisReplayGuard): every method below
simply lets a redis.RedisError propagate. RecomputeMachineSchedule.
execute_all() is the single place that decides what "the coordinator is
unavailable" means for the whole coalescing sequence; duplicating a
swallow-and-default policy in each of the four methods here would just
move that decision here instead, spread across four near-identical
try/excepts, for no benefit.
"""

from datetime import datetime
from typing import cast

import redis.asyncio

_GENERATION_KEY = "glados:schedule:recompute:gen"
_PROCESSED_KEY = "glados:schedule:recompute:processed"
# ISO timestamp of the first walk request after the last walk began.
_STALE_SINCE_KEY = "glados:schedule:recompute:stale_since"


class RedisScheduleRecomputeGenerationCounter:
    def __init__(self, client: redis.asyncio.Redis) -> None:
        self._redis = client

    async def increment_generation(self) -> int:
        return int(await self._redis.incr(_GENERATION_KEY))

    async def current_generation(self) -> int:
        value = cast("str | None", await self._redis.get(_GENERATION_KEY))
        return int(value) if value is not None else 0

    async def processed_generation(self) -> int:
        value = cast("str | None", await self._redis.get(_PROCESSED_KEY))
        return int(value) if value is not None else 0

    async def mark_processed(self, generation: int) -> None:
        await self._redis.set(_PROCESSED_KEY, generation)

    async def mark_stale(self, at: datetime) -> None:
        await self._redis.set(_STALE_SINCE_KEY, at.isoformat(), nx=True)

    async def take_stale_since(self) -> datetime | None:
        value = cast("str | None", await self._redis.getdel(_STALE_SINCE_KEY))
        return datetime.fromisoformat(value) if value is not None else None

    async def stale_since(self) -> datetime | None:
        value = cast("str | None", await self._redis.get(_STALE_SINCE_KEY))
        return datetime.fromisoformat(value) if value is not None else None
