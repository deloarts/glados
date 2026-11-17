"""
BackupScheduler: runs four interval jobs as background tasks in each
worker (src/modules/platform/infrastructure/interval_task.py). backup_tick
(60s) checks if a backup is due by calling
RunDueBackup. disk_space_check (15min) calls CheckDiskSpace to warn alert
recipients when "/" or the configured backup_path crosses
storage.disk_warning_percent. retention_purge (hourly) calls
PurgeExpiredRecords under an advisory lock, so only one worker purges per
hour. agent_token_sweep (hourly) revokes idle agent tokens and warns about
expiring ones under a lock of its own. Settings re-read from DB on every
tick.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable
from collections.abc import Callable
from collections.abc import Sequence
from dataclasses import dataclass

from src.modules.platform.adapters.outbound.external.login_attempts.redis_replay_guard import (
    RedisReplayGuard,
)
from src.modules.platform.adapters.outbound.external.mail.smtp_mail_service import SmtpMailService
from src.modules.platform.adapters.outbound.external.schedules.backup_jobs import (
    ScheduledBackupJobs,
)
from src.modules.platform.adapters.outbound.external.schedules.cron_schedule import (
    APSchedulerCronSchedule,
)
from src.modules.platform.adapters.outbound.external.system.psutil_stats_reader import (
    PsutilSystemStatsReader,
)
from src.modules.platform.adapters.outbound.persistence.advisory_lock import AdvisoryLockKey
from src.modules.platform.adapters.outbound.persistence.advisory_lock import advisory_lock
from src.modules.platform.adapters.outbound.persistence.repositories.agent_call_repository import (
    SqlAlchemyAgentCallRepository,
)
from src.modules.platform.adapters.outbound.persistence.repositories.api_key_repository import (
    SqlAlchemyApiKeyRepository,
)
from src.modules.platform.adapters.outbound.persistence.repositories.backup_run_repository import (
    SqlAlchemyBackupRunRepository,
)
from src.modules.platform.adapters.outbound.persistence.repositories.notification_repository import (
    SqlAlchemyNotificationRepository,
)
from src.modules.platform.adapters.outbound.persistence.repositories.pat_repository import (
    SqlAlchemyPatRepository,
)
from src.modules.platform.adapters.outbound.persistence.repositories.platform_settings_repository import (
    SqlAlchemyPlatformSettingsRepository,
)
from src.modules.platform.adapters.outbound.persistence.repositories.security_event_repository import (
    SqlAlchemySecurityEventRepository,
)
from src.modules.platform.adapters.outbound.persistence.repositories.user_repository import (
    SqlAlchemyUserRepository,
)
from src.modules.platform.adapters.outbound.persistence.retention_purger import (
    SqlAlchemyRetentionPurger,
)
from src.modules.platform.adapters.outbound.persistence.session import SessionLocal
from src.modules.platform.adapters.outbound.persistence.session import engine
from src.modules.platform.adapters.outbound.persistence.unit_of_work import SqlAlchemyUnitOfWork
from src.modules.platform.application.services.security_audit import SecurityAudit
from src.modules.platform.application.use_cases.agent.sweep_agent_tokens import SweepAgentTokens
from src.modules.platform.application.use_cases.backup.run_due_backup import RunDueBackup
from src.modules.platform.application.use_cases.system.check_disk_space import CheckDiskSpace
from src.modules.platform.application.use_cases.system.notify_schedule_error import (
    NotifyScheduleError,
)
from src.modules.platform.application.use_cases.system.purge_expired_records import (
    PurgeExpiredRecords,
)
from src.modules.platform.domain.entities.admin_settings.storage import AdminStorageSettings
from src.modules.platform.infrastructure.config.settings import cfg
from src.modules.platform.infrastructure.interval_task import run_every
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.infrastructure.process_identity import worker_identity
from src.modules.platform.infrastructure.redis_client import get_async_redis_client
from src.modules.platform.ports.outbound.backup_jobs_port import IBackupJobs

_TICK_INTERVAL_SECONDS = 60
_DISK_CHECK_INTERVAL_SECONDS = 15 * 60
_RETENTION_PURGE_INTERVAL_SECONDS = 60 * 60
_AGENT_TOKEN_SWEEP_INTERVAL_SECONDS = 60 * 60


@dataclass(frozen=True)
class IntervalJob:
    """One recurring job of the scheduler: the name run_every logs it
    under, the name of its background task, its interval and what it runs."""

    name: str
    task_name: str
    interval_seconds: float
    run: Callable[[], Awaitable[None]]


class BackupScheduler:
    def __init__(self, jobs: Sequence[IntervalJob] | None = None) -> None:
        """Runs the backup, disk space and retention purge jobs, or the
        given jobs instead, which lets a test run a job body of its own on
        an interval of its own through the same loop."""
        self._worker = worker_identity()
        self._jobs = tuple(jobs) if jobs is not None else self._default_jobs()

    @property
    def jobs(self) -> tuple[IntervalJob, ...]:
        """The jobs start() runs."""
        return self._jobs

    def _default_jobs(self) -> tuple[IntervalJob, ...]:
        return (
            IntervalJob("backup_tick", "backup-tick", _TICK_INTERVAL_SECONDS, self._tick),
            IntervalJob(
                "disk_space_check",
                "disk-space-check",
                _DISK_CHECK_INTERVAL_SECONDS,
                self._disk_check_tick,
            ),
            IntervalJob(
                "retention_purge",
                "retention-purge",
                _RETENTION_PURGE_INTERVAL_SECONDS,
                self._retention_purge_tick,
            ),
            IntervalJob(
                "agent_token_sweep",
                "agent-token-sweep",
                _AGENT_TOKEN_SWEEP_INTERVAL_SECONDS,
                self._agent_token_sweep_tick,
            ),
        )

    def start(self) -> list[asyncio.Task[None]]:
        """Starts the jobs as background tasks and returns them, for the
        lifespan to supervise and cancel on shutdown. Each runs once
        immediately (catch-up: a due time missed while the process was down
        is caught up within RunDueBackup's grace window) and then on its own
        interval, never overlapping itself
        (src/modules/platform/infrastructure/interval_task.py)."""
        return [
            asyncio.create_task(
                run_every(job.interval_seconds, job.run, job.name), name=job.task_name
            )
            for job in self._jobs
        ]

    async def _tick(self) -> None:
        try:
            async with SessionLocal() as db:
                settings_repo = SqlAlchemyPlatformSettingsRepository(db)
                await RunDueBackup(
                    settings_repo=settings_repo,
                    run_repo=SqlAlchemyBackupRunRepository(db),
                    jobs_factory=self._jobs_factory,
                    cron_schedule=APSchedulerCronSchedule(),
                    worker=self._worker,
                    notifier=await self._build_notifier(settings_repo),
                    uow=SqlAlchemyUnitOfWork(db),
                ).execute()
        except Exception as exc:
            # A tick must never kill the recurring job: log and let the next
            # one (60s away) retry, same fail-open shape as the outbox relay
            # and the notification task. Distinct from a *backup job*
            # failure (already alerted with task_name="backup" inside
            # RunClaimedBackup above); this is the tick itself breaking,
            # e.g. before RunDueBackup ever got to read settings.
            log.exception("BackupScheduler: tick failed.")
            await self._notify_tick_failure(str(exc))

    @staticmethod
    async def _build_notifier(
        settings_repo: SqlAlchemyPlatformSettingsRepository,
    ) -> NotifyScheduleError | None:
        """Best-effort: a failure to build the ops-alert notifier (e.g.
        mail settings not yet seeded on a brand new install) must never
        block the actual backup-due check RunDueBackup does: that is the
        primary job this tick exists for, alerting is secondary."""
        try:
            return NotifyScheduleError(
                mail_service=SmtpMailService(
                    await settings_repo.get_mail(), settings_repo=settings_repo
                ),
                replay_guard=RedisReplayGuard(get_async_redis_client()),
            )
        except Exception:
            log.warning(
                "BackupScheduler: failed to build the schedule-error notifier; "
                "alerts disabled for this tick.",
                exc_info=True,
            )
            return None

    async def _notify_tick_failure(self, message: str) -> None:
        """Best-effort alert for a BackupScheduler tick crash. Built fresh,
        on its own session/connection (the tick's own may be the broken
        thing), and must never itself raise back into the scheduler."""
        try:
            async with SessionLocal() as db:
                settings_repo = SqlAlchemyPlatformSettingsRepository(db)
                notifier = await self._build_notifier(settings_repo)
                if notifier is not None:
                    await notifier.execute("backup-scheduler", message)
        except Exception:
            log.exception("BackupScheduler: failed to send tick-failure alert.")

    async def _disk_check_tick(self) -> None:
        try:
            async with SessionLocal() as db:
                settings_repo = SqlAlchemyPlatformSettingsRepository(db)
                await CheckDiskSpace(
                    stats_reader=PsutilSystemStatsReader(),
                    admin_settings_repo=settings_repo,
                    mail_service=SmtpMailService(
                        await settings_repo.get_mail(), settings_repo=settings_repo
                    ),
                    replay_guard=RedisReplayGuard(get_async_redis_client()),
                ).execute()
        except Exception:
            # Same fail-open shape as _tick above: a bad reading must never
            # kill the recurring job.
            log.exception("BackupScheduler: disk space check failed.")

    async def _retention_purge_tick(self) -> None:
        try:
            async with advisory_lock(engine, AdvisoryLockKey.RETENTION_PURGE) as locked:
                if not locked:
                    return
                async with SessionLocal() as db:
                    await PurgeExpiredRecords(
                        settings_repo=SqlAlchemyPlatformSettingsRepository(db),
                        purger=SqlAlchemyRetentionPurger(db),
                    ).execute()
        except Exception:
            # Same fail-open shape as the other jobs: the next hourly run
            # picks up where this one stopped, since each batch commits.
            log.exception("BackupScheduler: retention purge failed.")

    async def _agent_token_sweep_tick(self) -> None:
        try:
            async with advisory_lock(engine, AdvisoryLockKey.AGENT_TOKEN_SWEEP) as locked:
                if not locked:
                    return
                async with SessionLocal() as db:
                    await SweepAgentTokens(
                        SqlAlchemyPlatformSettingsRepository(db),
                        SqlAlchemyPatRepository(db),
                        SqlAlchemyApiKeyRepository(db),
                        SqlAlchemyUserRepository(db),
                        SqlAlchemyAgentCallRepository(db),
                        SqlAlchemyNotificationRepository(db),
                        uow=SqlAlchemyUnitOfWork(db),
                        audit=SecurityAudit(SqlAlchemySecurityEventRepository(db)),
                    ).execute()
        except Exception:
            # Same fail-open shape as the other jobs: the next hourly run
            # sweeps again, since nothing is committed until it succeeds.
            log.exception("BackupScheduler: agent token sweep failed.")

    @staticmethod
    def _jobs_factory(settings: AdminStorageSettings) -> IBackupJobs:
        return ScheduledBackupJobs(settings=settings, db_url=cfg.database.url)
