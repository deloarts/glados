"""
Validates that backup is configured and that the actor has write:settings,
then claims a backup_runs row for "now" (trigger="manual") so the actual
run (RunClaimedBackup, same advisory-lock-guarded path a scheduled tick
uses) can happen in a FastAPI BackgroundTask after this returns. The
endpoint's HTTP response (202 or the errors below) happens synchronously;
only the pg_dump/upload work is deferred.
"""

from __future__ import annotations

from src.modules.platform.domain.entities.backup_run import BackupRun
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.exceptions import BackupAlreadyRunningError
from src.modules.platform.domain.exceptions import BackupNotConfiguredError
from src.modules.platform.domain.exceptions import InsufficientPermissionsError
from src.modules.platform.domain.value_objects.backup_run_status import BackupRunTrigger
from src.modules.platform.domain.value_objects.permission import Permission
from src.modules.platform.ports.outbound.platform_settings_repository import (
    IPlatformSettingsRepository,
)
from src.modules.platform.ports.outbound.repositories.backup_run_repository import (
    IBackupRunRepository,
)
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork
from src.shared_kernel.domain.services.clock import now_utc


class RunBackupNow:
    def __init__(
        self, repo: IPlatformSettingsRepository, run_repo: IBackupRunRepository, *, uow: IUnitOfWork
    ) -> None:
        self._repo = repo
        self._run_repo = run_repo
        self._uow = uow

    async def execute(self, actor: User, worker: str) -> BackupRun:
        """Returns the claimed run (caller runs its jobs in the background).
        Raises BackupNotConfiguredError, InsufficientPermissionsError, or
        BackupAlreadyRunningError (409, mapped in exception_handlers) when a
        run is already in progress. See that exception's docstring for why
        this check, and the claim below, are a UX gate rather than the real
        overlap-prevention mechanism."""
        if not actor.has_permission(Permission.WRITE_SETTINGS):
            raise InsufficientPermissionsError("write:settings required.")

        settings = await self._repo.get_storage()
        if not settings.backup_enabled or not settings.backup_path:
            raise BackupNotConfiguredError(
                "Backup is not enabled or backup_path is not configured."
            )

        if await self._run_repo.is_running():
            raise BackupAlreadyRunningError("A backup is already running.")

        run = await self._run_repo.try_claim(
            slot=now_utc(), trigger=BackupRunTrigger.MANUAL, worker=worker
        )
        # Committed before the response, so the background run, which opens
        # its own session, finds the claimed row.
        await self._uow.commit()
        if run is None:
            # Lost a race for this exact instant (another manual click, or a
            # scheduled tick whose due slot happened to land on the same
            # microsecond): same outcome as the is_running() check above.
            raise BackupAlreadyRunningError("A backup is already running.")
        return run
