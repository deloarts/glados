"""
Blocking advisory lock per PDM file id, on its own connection for the same
reason as every lock in advisory_lock.py. The key carries a fixed namespace
in its upper 32 bits and the file id in the lower ones, so it can never
collide with the single-key locks in AdvisoryLockKey.
"""

from contextlib import AbstractAsyncContextManager

from sqlalchemy.ext.asyncio import AsyncEngine

from src.modules.platform.adapters.outbound.persistence.advisory_lock import AdvisoryLockKey
from src.modules.platform.adapters.outbound.persistence.advisory_lock import advisory_lock_blocking


def pdm_file_lock_key(file_id: int) -> int:
    return (int(AdvisoryLockKey.PDM_FILE_NAMESPACE) << 32) | (file_id & 0xFFFFFFFF)


class SqlAlchemyPdmFileLock:
    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine

    def hold(self, file_id: int) -> AbstractAsyncContextManager[None]:
        return advisory_lock_blocking(self._engine, pdm_file_lock_key(file_id))
