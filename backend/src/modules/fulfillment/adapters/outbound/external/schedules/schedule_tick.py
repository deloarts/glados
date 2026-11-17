"""
The periodic walk of the production schedule: every 15 minutes and once
right after midnight in the tenant's timezone, so the dates catch up when no
write requested a walk, such as a new day moving "today", and when the
`schedule` event worker was down. The
tick runs in every worker every minute and walks when one is due; the
walk's generation coalescing and its advisory lock make the other workers'
walks skip.
"""

import time
from collections.abc import Awaitable
from collections.abc import Callable
from datetime import date

TICK_SECONDS = 60
WALK_EVERY_SECONDS = 15 * 60


class ScheduleTick:
    def __init__(
        self,
        walk: Callable[[], Awaitable[object]],
        tenant_today: Callable[[], Awaitable[date]],
        *,
        every_seconds: float = WALK_EVERY_SECONDS,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._walk = walk
        self._tenant_today = tenant_today
        self._every = every_seconds
        self._clock = clock
        self._last_walk: float | None = None
        self._last_day: date | None = None

    async def __call__(self) -> None:
        today = await self._tenant_today()
        now = self._clock()
        due = (
            self._last_walk is None
            or now - self._last_walk >= self._every
            or today != self._last_day
        )
        if not due:
            return
        await self._walk()
        self._last_walk = now
        self._last_day = today
