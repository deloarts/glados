"""
Abstract interface for backup run persistence. STALE_AFTER defines how long a
run may sit in the `running` state before it is treated as an abandoned
worker rather than a slow backup.
"""

from contextlib import AbstractAsyncContextManager
from datetime import datetime
from datetime import timedelta
from typing import Protocol
from typing import runtime_checkable

from src.modules.platform.domain.entities.backup_run import BackupRun
from src.modules.platform.domain.value_objects.backup_run_status import BackupRunStatus
from src.modules.platform.domain.value_objects.backup_run_status import BackupRunTrigger

# A `running` row nobody ever finished (worker OOM'd mid pg_dump, was
# killed, the box rebooted) must not block every future run-now/tick
# forever. 2h is comfortably longer than any realistic dump+upload, so a
# row still `running` past that age is not a slow backup, it is a dead
# worker. Lives here (a port, not an adapter) so both RunDueBackup
# (application layer, calls mark_stale_failed with this as its cutoff) and
# SqlAlchemyBackupRunRepository (adapter, uses it inside is_running()) can
# import one shared value without either layer reaching into the other.
STALE_AFTER = timedelta(hours=2)


@runtime_checkable
class IBackupRunRepository(Protocol):
    async def try_claim(
        self, slot: datetime, trigger: BackupRunTrigger, worker: str
    ) -> BackupRun | None:
        """`INSERT ... ON CONFLICT (slot) DO NOTHING`: claims the row for
        this slot and returns it, or returns None when another worker (or
        an earlier claim of this exact slot) already owns it. Commits."""
        ...

    def run_lock(self) -> AbstractAsyncContextManager[bool]:
        """PG advisory lock (on a dedicated connection, not any Session;
        see advisory_lock.py) guarding the actual job execution, so a
        manual run-now can never overlap a scheduled tick (or another
        manual run). Yields True (locked) or False (already held
        elsewhere); always True on a non-postgresql dialect. Released when
        the `async with` block exits, regardless of how."""
        ...

    async def finish(
        self,
        run_id: int,
        status: BackupRunStatus,
        db_key: str | None,
        files_key: str | None,
        error: str | None,
    ) -> None:
        """Marks a claimed row terminal (BackupRunStatus.SUCCESS or
        .FAILED) and stamps finished_at. Commits."""
        ...

    async def latest(self, limit: int) -> list[BackupRun]:
        """Most recent runs first (any status), newest to oldest."""
        ...

    async def last_success(self) -> BackupRun | None: ...

    async def last_failure(self) -> BackupRun | None: ...

    async def is_running(self) -> bool:
        """Best-effort check for the run-now endpoint's 409; see
        BackupAlreadyRunningError's docstring for why this is a UX gate,
        not the actual overlap-prevention mechanism. Only counts `running`
        rows younger than STALE_AFTER: an older one is presumed dead (see
        mark_stale_failed), not actually in progress."""
        ...

    async def mark_stale_failed(self, older_than: datetime) -> int:
        """Marks every `running` row with started_at < older_than as
        `failed` (error="worker died or timed out"). Returns the count
        fixed, so the caller can log when it actually found something.
        Commits."""
        ...
