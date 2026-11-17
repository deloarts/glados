"""
One scheduled-tick pass: marks any stale `running` row failed (a dead
worker's leftover), then computes the latest cron-due backup slot and, if
one exists and nobody else has already claimed it, runs it. Safe to call
every 60s from every one of gunicorn's four worker processes: the
backup_runs.slot UNIQUE constraint (IBackupRunRepository.try_claim) is what
makes at most one of those calls actually run the jobs, not any locking
done here.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from datetime import timedelta

from src.modules.platform.application.use_cases.backup.run_claimed_backup import RunClaimedBackup
from src.modules.platform.application.use_cases.system.notify_schedule_error import (
    NotifyScheduleError,
)
from src.modules.platform.domain.entities.admin_settings.storage import AdminStorageSettings
from src.modules.platform.domain.value_objects.backup_run_status import BackupRunTrigger
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.ports.outbound.backup_jobs_port import IBackupJobs
from src.modules.platform.ports.outbound.cron_schedule_port import ICronSchedule
from src.modules.platform.ports.outbound.platform_settings_repository import (
    IPlatformSettingsRepository,
)
from src.modules.platform.ports.outbound.repositories.backup_run_repository import STALE_AFTER
from src.modules.platform.ports.outbound.repositories.backup_run_repository import (
    IBackupRunRepository,
)
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork
from src.shared_kernel.domain.services.clock import now_utc

# A due time older than this is treated as missed, not caught up, so a
# scheduler that was down for hours does not fire a stale backup on restart.
GRACE = timedelta(hours=1)


class RunDueBackup:
    def __init__(
        self,
        settings_repo: IPlatformSettingsRepository,
        run_repo: IBackupRunRepository,
        jobs_factory: Callable[[AdminStorageSettings], IBackupJobs],
        cron_schedule: ICronSchedule,
        worker: str,
        notifier: NotifyScheduleError | None = None,
        *,
        uow: IUnitOfWork,
    ) -> None:
        self._settings_repo = settings_repo
        self._uow = uow
        self._run_repo = run_repo
        self._jobs_factory = jobs_factory
        self._cron_schedule = cron_schedule
        self._worker = worker
        # Optional, default None = skip, threaded straight through to
        # RunClaimedBackup below.
        self._notifier = notifier

    async def execute(self, now: datetime | None = None) -> None:
        now = now or now_utc()

        # A worker that died mid-backup (OOM during pg_dump, killed,
        # rebooted) leaves its row `running` forever, which would make
        # is_running() answer 409 forever too. Run this before anything
        # else so it self-heals every tick, independent of whether backup
        # is even still enabled below.
        fixed = await self._run_repo.mark_stale_failed(older_than=now - STALE_AFTER)
        await self._uow.commit()
        if fixed:
            log.warning(
                "RunDueBackup: marked %d stale 'running' backup_runs row(s) failed "
                "(started_at older than %s ago -- presumed a dead worker).",
                fixed,
                STALE_AFTER,
            )

        settings = await self._settings_repo.get_storage()
        if not settings.backup_enabled or not settings.backup_cron or not settings.backup_path:
            return

        due = self._cron_schedule.latest_due(settings.backup_cron, now, GRACE)
        if due is None:
            return

        run = await self._run_repo.try_claim(
            slot=due, trigger=BackupRunTrigger.SCHEDULED, worker=self._worker
        )
        # The claim commits on its own, before the jobs start, so every other
        # worker's claim of the same slot conflicts with a committed row.
        await self._uow.commit()
        if run is None:
            log.debug("Backup slot %s already claimed; skipping this tick.", due)
            return

        jobs = self._jobs_factory(settings)
        await RunClaimedBackup(
            self._run_repo, jobs, notifier=self._notifier, uow=self._uow
        ).execute(run.id)
