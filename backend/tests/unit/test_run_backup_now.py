"""
Unit tests for the RunBackupNow use case: permission and configuration
checks (unchanged behaviour) plus the claim path, where is_running()
gates first, then try_claim(slot=now, trigger="manual"), both raising
BackupAlreadyRunningError (409, see exception_handlers._STATUS).
"""

from datetime import datetime

import pytest

from src.modules.platform.application.use_cases.admin_settings.run_backup_now import RunBackupNow
from src.modules.platform.domain.entities.admin_settings.storage import AdminStorageSettings
from src.modules.platform.domain.entities.backup_run import BackupRun
from src.modules.platform.domain.exceptions import BackupAlreadyRunningError
from src.modules.platform.domain.exceptions import BackupNotConfiguredError
from src.modules.platform.domain.exceptions import InsufficientPermissionsError
from src.modules.platform.domain.value_objects.backup_run_status import BackupRunStatus
from src.modules.platform.domain.value_objects.backup_run_status import BackupRunTrigger
from src.modules.platform.domain.value_objects.permission import Permission
from tests.factories import make_user
from tests.unit.fakes import FakeUnitOfWork


def make_storage(**kwargs) -> AdminStorageSettings:
    defaults = dict(
        id=1,
        provider="local",
        enabled=True,
        endpoint_url=None,
        public_endpoint_url=None,
        bucket_name=None,
        access_key=None,
        secret_key=None,
        region=None,
        use_ssl=False,
        backup_enabled=True,
        backup_path="backups",
        backup_cron="0 2 * * *",
        backup_retention_count=7,
    )
    defaults.update(kwargs)
    return AdminStorageSettings(**defaults)


class FakeSettingsRepo:
    def __init__(self, storage: AdminStorageSettings) -> None:
        self._storage = storage

    async def get_storage(self) -> AdminStorageSettings:
        return self._storage


class FakeRunRepo:
    def __init__(
        self, *, running: bool = False, claim_returns: BackupRun | str | None = "auto"
    ) -> None:
        self.running = running
        self.claim_returns = claim_returns
        self.claim_calls: list[tuple[datetime, str, str]] = []

    async def is_running(self) -> bool:
        return self.running

    async def try_claim(
        self, slot: datetime, trigger: BackupRunTrigger, worker: str
    ) -> BackupRun | None:
        self.claim_calls.append((slot, trigger, worker))
        if self.claim_returns != "auto":
            return self.claim_returns
        return BackupRun(
            id=1,
            slot=slot,
            trigger=trigger,
            started_at=slot,
            finished_at=None,
            status=BackupRunStatus.RUNNING,
            db_key=None,
            files_key=None,
            error=None,
            worker=worker,
        )


class TestPermission:
    async def test_actor_without_write_settings_is_rejected(self):
        use_case = RunBackupNow(
            FakeSettingsRepo(make_storage()), FakeRunRepo(), uow=FakeUnitOfWork()
        )

        with pytest.raises(InsufficientPermissionsError):
            await use_case.execute(make_user(permissions=[]), worker="host-1")


class TestNotConfigured:
    async def test_backup_disabled_raises(self):
        use_case = RunBackupNow(
            FakeSettingsRepo(make_storage(backup_enabled=False)),
            FakeRunRepo(),
            uow=FakeUnitOfWork(),
        )

        with pytest.raises(BackupNotConfiguredError):
            await use_case.execute(
                make_user(permissions=[Permission.WRITE_SETTINGS]), worker="host-1"
            )

    async def test_missing_backup_path_raises(self):
        use_case = RunBackupNow(
            FakeSettingsRepo(make_storage(backup_path=None)), FakeRunRepo(), uow=FakeUnitOfWork()
        )

        with pytest.raises(BackupNotConfiguredError):
            await use_case.execute(
                make_user(permissions=[Permission.WRITE_SETTINGS]), worker="host-1"
            )


class TestAlreadyRunning:
    async def test_is_running_true_raises_before_ever_claiming(self):
        run_repo = FakeRunRepo(running=True)
        use_case = RunBackupNow(FakeSettingsRepo(make_storage()), run_repo, uow=FakeUnitOfWork())

        with pytest.raises(BackupAlreadyRunningError):
            await use_case.execute(
                make_user(permissions=[Permission.WRITE_SETTINGS]), worker="host-1"
            )

        assert run_repo.claim_calls == []  # never even tried to claim

    async def test_lost_claim_race_also_raises(self):
        run_repo = FakeRunRepo(running=False, claim_returns=None)
        use_case = RunBackupNow(FakeSettingsRepo(make_storage()), run_repo, uow=FakeUnitOfWork())

        with pytest.raises(BackupAlreadyRunningError):
            await use_case.execute(
                make_user(permissions=[Permission.WRITE_SETTINGS]), worker="host-1"
            )


class TestSuccess:
    async def test_claims_now_with_manual_trigger_and_the_given_worker(self):
        run_repo = FakeRunRepo()
        use_case = RunBackupNow(FakeSettingsRepo(make_storage()), run_repo, uow=FakeUnitOfWork())

        run = await use_case.execute(
            make_user(permissions=[Permission.WRITE_SETTINGS]), worker="host-7"
        )

        (call,) = run_repo.claim_calls
        _slot, trigger, worker = call
        assert trigger == BackupRunTrigger.MANUAL
        assert worker == "host-7"
        assert run.id == 1
