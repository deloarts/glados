"""
Runs the two backup jobs for an already-claimed backup_runs row. Shared by
RunDueBackup (scheduled ticks) and the run-now endpoint (manual trigger), so
both paths get identical overlap protection and identical bookkeeping.

The advisory lock (IBackupRunRepository.run_lock) is the actual
data-integrity guarantee: a manual run-now can never run its jobs
concurrently with a scheduled tick's jobs (or another manual run), because
whichever of them loses the lock marks its already-claimed row `failed`
with `error="another backup is running"` and does nothing else: it never
retries and never leaves the row `running` forever. Held for the whole job
run + finish() below on its own dedicated connection (see advisory_lock.py),
never the session the unit of work commits finish() on, so the two don't
interfere. The read transaction is committed before the jobs start, and
every outcome is recorded by finish() and committed in its own short
transaction afterwards.
"""

from __future__ import annotations

from src.modules.platform.application.use_cases.system.notify_schedule_error import (
    NotifyScheduleError,
)
from src.modules.platform.domain.value_objects.backup_run_status import BackupRunStatus
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.ports.outbound.backup_jobs_port import IBackupJobs
from src.modules.platform.ports.outbound.repositories.backup_run_repository import (
    IBackupRunRepository,
)
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork

_MAX_ERROR_CHARS = 500  # a driver/subprocess traceback string must not become the stored error


class RunClaimedBackup:
    def __init__(
        self,
        run_repo: IBackupRunRepository,
        jobs: IBackupJobs,
        notifier: NotifyScheduleError | None = None,
        *,
        uow: IUnitOfWork,
    ) -> None:
        self._run_repo = run_repo
        self._jobs = jobs
        self._uow = uow
        # Optional, None skips the failure alert, the same pattern as
        # HandleEventNotifications' optional mail wiring.
        self._notifier = notifier

    async def execute(self, run_id: int) -> None:
        async with self._run_repo.run_lock() as locked:
            if not locked:
                log.warning(
                    "Backup run id=%s: another backup is already running, marking failed.", run_id
                )
                await self._run_repo.finish(
                    run_id,
                    status=BackupRunStatus.FAILED,
                    db_key=None,
                    files_key=None,
                    error="another backup is running",
                )
                await self._uow.commit()
                return

            # The jobs run for minutes without touching this session. Ending
            # whatever read transaction the caller left open keeps the server
            # from terminating it as idle, which would make finish() fail and
            # leave the row `running`. The lock lives on its own connection.
            await self._uow.commit()
            try:
                db_key = await self._jobs.run_db()
                files_key = await self._jobs.run_files()
            except Exception as exc:
                log.exception("Backup run id=%s failed.", run_id)
                error = str(exc)[:_MAX_ERROR_CHARS]
                await self._run_repo.finish(
                    run_id,
                    status=BackupRunStatus.FAILED,
                    db_key=None,
                    files_key=None,
                    error=error,
                )
                await self._uow.commit()
                if self._notifier is not None:
                    await self._notifier.execute("backup", error)
                return

            await self._run_repo.finish(
                run_id,
                status=BackupRunStatus.SUCCESS,
                db_key=db_key,
                files_key=files_key,
                error=None,
            )
            await self._uow.commit()
            log.info("Backup run id=%s complete: db=%r files=%r", run_id, db_key, files_key)
