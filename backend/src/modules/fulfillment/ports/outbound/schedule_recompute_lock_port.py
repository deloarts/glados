"""
Exclusive lock held over one whole schedule recompute (generation check,
walk, persist and commit), so recomputes across worker processes serialize
instead of racing. It works with IScheduleRecomputeGenerationCounter, as
described in RecomputeMachineSchedule's module docstring.

Unlike the other advisory locks, which try and skip, this one blocks: a
caller learns that its walk is redundant only from processed_generation()
once it holds the lock, so skipping a busy lock would bring back the
duplicate walk.
"""

from contextlib import AbstractAsyncContextManager
from typing import Protocol


class IScheduleRecomputeLock(Protocol):
    def lock(self) -> AbstractAsyncContextManager[None]:
        """Blocks until the lock is acquired and releases it when the `with`
        block exits. A no-op on SQLite; see advisory_lock.py."""
        ...
