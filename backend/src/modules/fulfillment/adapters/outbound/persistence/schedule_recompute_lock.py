"""
IScheduleRecomputeLock over a dedicated connection, via advisory_lock.py's
advisory_lock_blocking(), the BLOCKING pg_advisory_xact_lock variant, not
the try-and-skip pg_try_advisory_xact_lock every other lock in this package
uses. See recompute_machine_schedule.py's docstring for why the recompute
walk needs a real wait-your-turn lock rather than a "someone else already
has it, never mind" one, and advisory_lock.py's own docstring for why this
always runs on a dedicated connection rather than the session doing the
actual walk/persist/commit: a session-level lock leaks through this
app's connection pool instead of releasing when its transaction ends.
"""

from contextlib import AbstractAsyncContextManager

from sqlalchemy.ext.asyncio import AsyncEngine

from src.modules.platform.adapters.outbound.persistence.advisory_lock import AdvisoryLockKey
from src.modules.platform.adapters.outbound.persistence.advisory_lock import advisory_lock_blocking


class SqlAlchemyScheduleRecomputeLock:
    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine

    def lock(self) -> AbstractAsyncContextManager[None]:
        return advisory_lock_blocking(self._engine, AdvisoryLockKey.SCHEDULE_RECOMPUTE)
