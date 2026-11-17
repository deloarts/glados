"""
Advisory lock guarding one PDM poll tick, same try-and-skip shape as
notification_lock.py (see that module's docstring for the full "why a
dedicated connection" rationale). PdmPollScheduler ticks every 60s on
every gunicorn worker, but only the worker whose tick finds the vault due
(RunPdmPollIfDue) should actually run PollPdmVault.
"""

from contextlib import AbstractAsyncContextManager

from sqlalchemy.ext.asyncio import AsyncEngine

from src.modules.platform.adapters.outbound.persistence.advisory_lock import AdvisoryLockKey
from src.modules.platform.adapters.outbound.persistence.advisory_lock import advisory_lock


class SqlAlchemyPdmPollLock:
    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine

    def lock(self) -> AbstractAsyncContextManager[bool]:
        return advisory_lock(self._engine, AdvisoryLockKey.PDM_POLL)
