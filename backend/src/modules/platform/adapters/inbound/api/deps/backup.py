"""Use case factories for the Backup tab: listing, downloading, starting and
restoring backups, and RunClaimedBackup for the run-now endpoint's
background task. That task opens its own database session after the
request has already been answered, so it cannot take a request-scoped
repository the normal Depends(get_x_repo) way, it needs a callable it can
hand a session to once that session exists. The jobs factory resolves through the
ordinary request-scoped dependency graph, so tests override it the usual
way.
"""

from collections.abc import Awaitable
from collections.abc import Callable

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.platform.adapters.inbound.api.deps.database import get_unit_of_work
from src.modules.platform.adapters.inbound.api.deps.repositories import get_backup_run_repo
from src.modules.platform.adapters.inbound.api.deps.repositories import get_platform_settings_repo
from src.modules.platform.adapters.inbound.api.deps.services import get_backup_jobs_factory
from src.modules.platform.adapters.inbound.api.deps.services import get_storage_adapter_factory
from src.modules.platform.adapters.outbound.external.login_attempts.redis_replay_guard import (
    RedisReplayGuard,
)
from src.modules.platform.adapters.outbound.external.mail.smtp_mail_service import SmtpMailService
from src.modules.platform.adapters.outbound.persistence.repositories.backup_run_repository import (
    SqlAlchemyBackupRunRepository,
)
from src.modules.platform.adapters.outbound.persistence.repositories.platform_settings_repository import (
    SqlAlchemyPlatformSettingsRepository,
)
from src.modules.platform.adapters.outbound.persistence.unit_of_work import SqlAlchemyUnitOfWork
from src.modules.platform.application.use_cases.admin_settings.download_backup import DownloadBackup
from src.modules.platform.application.use_cases.admin_settings.list_backups import ListBackups
from src.modules.platform.application.use_cases.admin_settings.restore_files import RestoreFiles
from src.modules.platform.application.use_cases.admin_settings.run_backup_now import RunBackupNow
from src.modules.platform.application.use_cases.backup.run_claimed_backup import RunClaimedBackup
from src.modules.platform.application.use_cases.system.notify_schedule_error import (
    NotifyScheduleError,
)
from src.modules.platform.infrastructure.config.settings import cfg
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.infrastructure.redis_client import get_async_redis_client
from src.modules.platform.ports.outbound.backup_jobs_port import IBackupJobsFactory
from src.modules.platform.ports.outbound.platform_settings_repository import (
    IPlatformSettingsRepository,
)
from src.modules.platform.ports.outbound.repositories.backup_run_repository import (
    IBackupRunRepository,
)
from src.modules.platform.ports.outbound.storage_port import IStorageAdapterFactory
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork


def get_run_claimed_backup_factory(
    jobs_factory: IBackupJobsFactory = Depends(get_backup_jobs_factory),
) -> Callable[[AsyncSession], Awaitable[RunClaimedBackup]]:
    """Returns an async callable that builds a fully wired RunClaimedBackup
    from whatever session the caller opens for itself; it awaits the storage
    and mail settings reads."""

    async def factory(db: AsyncSession) -> RunClaimedBackup:
        settings_repo = SqlAlchemyPlatformSettingsRepository(db)
        settings = await settings_repo.get_storage()
        jobs = jobs_factory(settings=settings, db_url=cfg.database.url)
        # Best-effort: a failure to build the ops-alert notifier (e.g.
        # mail settings not yet seeded) must never block the actual
        # backup, which is the whole point of this endpoint.
        notifier = None
        try:
            notifier = NotifyScheduleError(
                mail_service=SmtpMailService(
                    await settings_repo.get_mail(), settings_repo=settings_repo
                ),
                replay_guard=RedisReplayGuard(get_async_redis_client()),
            )
        except Exception:
            log.warning(
                "Failed to build the schedule-error notifier for a manual backup run; "
                "alerts disabled for this run.",
                exc_info=True,
            )
        return RunClaimedBackup(
            SqlAlchemyBackupRunRepository(db), jobs, notifier=notifier, uow=SqlAlchemyUnitOfWork(db)
        )

    return factory


def get_list_backups_use_case(
    repo: IPlatformSettingsRepository = Depends(get_platform_settings_repo),
    storage_factory: IStorageAdapterFactory = Depends(get_storage_adapter_factory),
    run_repo: IBackupRunRepository = Depends(get_backup_run_repo),
) -> ListBackups:
    return ListBackups(
        repo,
        storage_factory,
        run_repo,
        encryption_key_configured=bool(cfg.security.backup_encryption_key),
    )


def get_download_backup_use_case(
    repo: IPlatformSettingsRepository = Depends(get_platform_settings_repo),
    storage_factory: IStorageAdapterFactory = Depends(get_storage_adapter_factory),
) -> DownloadBackup:
    return DownloadBackup(repo, storage_factory)


def get_run_backup_now_use_case(
    repo: IPlatformSettingsRepository = Depends(get_platform_settings_repo),
    run_repo: IBackupRunRepository = Depends(get_backup_run_repo),
    uow: IUnitOfWork = Depends(get_unit_of_work),
) -> RunBackupNow:
    return RunBackupNow(repo, run_repo, uow=uow)


def get_restore_files_use_case(
    repo: IPlatformSettingsRepository = Depends(get_platform_settings_repo),
    storage_factory: IStorageAdapterFactory = Depends(get_storage_adapter_factory),
    uow: IUnitOfWork = Depends(get_unit_of_work),
) -> RestoreFiles:
    return RestoreFiles(repo, storage_factory, uow=uow)
