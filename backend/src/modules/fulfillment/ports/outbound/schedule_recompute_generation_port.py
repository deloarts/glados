"""
Redis-backed generation counter behind RecomputeMachineSchedule's walk
coalescing (its module docstring has the design). A later caller in a burst
of execute_all() calls uses it to see that an earlier walk already covered
its data and skips its own walk.

Each call increments the generation first. A caller that goes on to walk
samples current_generation() again once it holds the lock and before it
reads orders, so the value it records covers every commit up to then.
processed_generation() and mark_processed() keep the low-water mark of the
last completed walk. Redis errors propagate; execute_all() alone decides to
fall back to walking unconditionally.
"""

from datetime import datetime
from typing import Protocol


class IScheduleRecomputeGenerationCounter(Protocol):
    async def increment_generation(self) -> int:
        """Atomically advances the shared generation counter by one and
        returns the new value."""
        ...

    async def current_generation(self) -> int:
        """The generation counter's current value, without advancing it.
        0 if it has never been incremented."""
        ...

    async def processed_generation(self) -> int:
        """The generation covered by the most recently completed walk. 0 if
        no walk has ever recorded one."""
        ...

    async def mark_processed(self, generation: int) -> None:
        """Records that a walk covering up to `generation` has completed."""
        ...

    async def mark_stale(self, at: datetime) -> None:
        """Records that the stored schedule is stale since `at`, unless an
        earlier moment is recorded already."""
        ...

    async def take_stale_since(self) -> datetime | None:
        """Clears the stale mark, for a walk about to read the orders, and
        returns it; a request after this marks the schedule stale again."""
        ...

    async def stale_since(self) -> datetime | None:
        """Since when the stored schedule awaits a walk, None when no request
        is pending."""
        ...
