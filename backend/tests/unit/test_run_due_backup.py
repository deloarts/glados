"""
Unit tests for RunDueBackup: the scheduled-tick orchestration (claim a due
slot, run its jobs under the advisory lock, finish the row) with fake
settings/repo/jobs/cron_schedule, no database, no APScheduler. The cron
grace-window arithmetic itself is covered separately in
test_cron_schedule.py (the real APSchedulerCronSchedule), since RunDueBackup
only ever calls ICronSchedule.latest_due and trusts what it returns.
"""

import logging
from contextlib import asynccontextmanager
from datetime import UTC
from datetime import datetime
from datetime import timedelta

from src.modules.platform.application.use_cases.backup.run_due_backup import RunDueBackup
from src.modules.platform.domain.entities.admin_settings.storage import AdminStorageSettings
from src.modules.platform.domain.entities.backup_run import BackupRun
from src.modules.platform.domain.value_objects.backup_run_status import BackupRunStatus
from src.modules.platform.domain.value_objects.backup_run_status import BackupRunTrigger
from src.modules.platform.ports.outbound.repositories.backup_run_repository import STALE_AFTER
from tests.unit.fakes import FakeUnitOfWork

NOW = datetime(2026, 8, 28, 10, 13, 0, tzinfo=UTC)
DUE = NOW - timedelta(minutes=3)


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


class FakeCronSchedule:
    def __init__(self, due: datetime | None) -> None:
        self.due = due
        self.calls: list[tuple[str, datetime, timedelta]] = []

    def latest_due(self, cron: str, now: datetime, grace: timedelta) -> datetime | None:
        self.calls.append((cron, now, grace))
        return self.due


class FakeBackupRunRepo:
    def __init__(self, *, lock_available: bool = True, stale_fixed_count: int = 0) -> None:
        self._claimed_slots: set[datetime] = set()
        self._next_id = 1
        self.lock_available = lock_available
        self.stale_fixed_count = stale_fixed_count
        self.claim_calls: list[tuple[datetime, str, str]] = []
        self.finish_calls: list[tuple[int, str, str | None, str | None, str | None]] = []
        self.mark_stale_failed_calls: list[datetime] = []

    async def try_claim(
        self, slot: datetime, trigger: BackupRunTrigger, worker: str
    ) -> BackupRun | None:
        self.claim_calls.append((slot, trigger, worker))
        if slot in self._claimed_slots:
            return None
        self._claimed_slots.add(slot)
        run_id = self._next_id
        self._next_id += 1
        return BackupRun(
            id=run_id,
            slot=slot,
            trigger=trigger,
            started_at=datetime.now(UTC),
            finished_at=None,
            status=BackupRunStatus.RUNNING,
            db_key=None,
            files_key=None,
            error=None,
            worker=worker,
        )

    @asynccontextmanager
    async def run_lock(self):
        yield self.lock_available

    async def finish(
        self,
        run_id: int,
        status: BackupRunStatus,
        db_key: str | None,
        files_key: str | None,
        error: str | None,
    ) -> None:
        self.finish_calls.append((run_id, status, db_key, files_key, error))

    async def latest(self, limit: int) -> list[BackupRun]:
        raise NotImplementedError

    async def last_success(self) -> BackupRun | None:
        raise NotImplementedError

    async def last_failure(self) -> BackupRun | None:
        raise NotImplementedError

    async def is_running(self) -> bool:
        raise NotImplementedError

    async def mark_stale_failed(self, older_than: datetime) -> int:
        self.mark_stale_failed_calls.append(older_than)
        return self.stale_fixed_count


class FakeJobs:
    def __init__(self, *, raises: Exception | None = None) -> None:
        self.raises = raises
        self.db_ran = False
        self.files_ran = False

    async def run_db(self) -> str:
        if self.raises:
            raise self.raises
        self.db_ran = True
        return "backups/db/x.sql.gz"

    async def run_files(self) -> str:
        self.files_ran = True
        return "backups/files/x/"


def build(
    *,
    storage: AdminStorageSettings | None = None,
    due: datetime | None = DUE,
    run_repo: FakeBackupRunRepo | None = None,
    jobs: FakeJobs | None = None,
) -> tuple[RunDueBackup, FakeBackupRunRepo, FakeJobs]:
    run_repo = run_repo if run_repo is not None else FakeBackupRunRepo()
    jobs = jobs if jobs is not None else FakeJobs()
    use_case = RunDueBackup(
        settings_repo=FakeSettingsRepo(storage or make_storage()),
        run_repo=run_repo,
        jobs_factory=lambda _settings: jobs,
        cron_schedule=FakeCronSchedule(due),
        worker="host-123",
        uow=FakeUnitOfWork(),
    )
    return use_case, run_repo, jobs


class TestBackupNotConfigured:
    async def test_backup_disabled_never_claims(self):
        use_case, run_repo, jobs = build(storage=make_storage(backup_enabled=False))

        await use_case.execute(now=NOW)

        assert run_repo.claim_calls == []
        assert jobs.db_ran is False

    async def test_no_cron_never_claims(self):
        use_case, run_repo, _jobs = build(storage=make_storage(backup_cron=None))

        await use_case.execute(now=NOW)

        assert run_repo.claim_calls == []

    async def test_no_backup_path_never_claims(self):
        use_case, run_repo, _jobs = build(storage=make_storage(backup_path=None))

        await use_case.execute(now=NOW)

        assert run_repo.claim_calls == []


class TestNoDueTime:
    async def test_none_from_cron_schedule_never_claims(self):
        use_case, run_repo, jobs = build(due=None)

        await use_case.execute(now=NOW)

        assert run_repo.claim_calls == []
        assert jobs.db_ran is False


class TestDueSlotClaimedAndRun:
    async def test_claims_the_due_slot_with_scheduled_trigger_and_worker(self):
        use_case, run_repo, _jobs = build()

        await use_case.execute(now=NOW)

        (call,) = run_repo.claim_calls
        assert call == (DUE, BackupRunTrigger.SCHEDULED, "host-123")

    async def test_runs_both_jobs_and_finishes_success(self):
        use_case, run_repo, jobs = build()

        await use_case.execute(now=NOW)

        assert jobs.db_ran is True
        assert jobs.files_ran is True
        (call,) = run_repo.finish_calls
        _run_id, status, db_key, files_key, error = call
        assert status == BackupRunStatus.SUCCESS
        assert db_key == "backups/db/x.sql.gz"
        assert files_key == "backups/files/x/"
        assert error is None


class TestClaimLost:
    async def test_slot_already_claimed_skips_running_jobs(self):
        run_repo = FakeBackupRunRepo()
        run_repo._claimed_slots.add(DUE)  # simulate another worker's claim
        use_case, _, jobs = build(run_repo=run_repo)

        await use_case.execute(now=NOW)

        assert jobs.db_ran is False
        assert run_repo.finish_calls == []

    async def test_two_ticks_for_the_same_slot_run_the_jobs_only_once(self):
        run_repo = FakeBackupRunRepo()
        jobs = FakeJobs()
        use_case = RunDueBackup(
            settings_repo=FakeSettingsRepo(make_storage()),
            run_repo=run_repo,
            jobs_factory=lambda _s: jobs,
            cron_schedule=FakeCronSchedule(DUE),
            worker="host-123",
            uow=FakeUnitOfWork(),
        )

        await use_case.execute(now=NOW)
        first_finish_count = len(run_repo.finish_calls)
        await use_case.execute(now=NOW)  # second worker's tick, same due slot

        assert len(run_repo.claim_calls) == 2
        assert first_finish_count == 1
        assert len(run_repo.finish_calls) == 1  # unchanged: second tick never ran/finished


class FakeNotifier:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    async def execute(self, task_name: str, message: str) -> None:
        self.calls.append((task_name, message))


class TestJobFailure:
    async def test_a_raising_job_marks_the_row_failed_with_the_error(self):
        use_case, run_repo, _jobs = build(jobs=FakeJobs(raises=RuntimeError("pg_dump exploded")))

        await use_case.execute(now=NOW)

        (call,) = run_repo.finish_calls
        _run_id, status, db_key, files_key, error = call
        assert status == BackupRunStatus.FAILED
        assert db_key is None
        assert files_key is None
        assert error is not None and "pg_dump exploded" in error

    async def test_the_configured_notifier_is_passed_through_to_run_claimed_backup(self):
        """RunDueBackup's own optional `notifier` constructor arg must
        reach RunClaimedBackup, the class that
        actually calls it on a job failure."""
        notifier = FakeNotifier()
        run_repo = FakeBackupRunRepo()
        jobs = FakeJobs(raises=RuntimeError("pg_dump exploded"))
        use_case = RunDueBackup(
            settings_repo=FakeSettingsRepo(make_storage()),
            run_repo=run_repo,
            jobs_factory=lambda _s: jobs,
            cron_schedule=FakeCronSchedule(DUE),
            worker="host-123",
            notifier=notifier,
            uow=FakeUnitOfWork(),
        )

        await use_case.execute(now=NOW)

        assert notifier.calls == [("backup", "pg_dump exploded")]

    async def test_no_notifier_is_the_old_behaviour(self):
        use_case, run_repo, _jobs = build(jobs=FakeJobs(raises=RuntimeError("boom")))

        await use_case.execute(now=NOW)  # must not raise despite no notifier configured

        assert len(run_repo.finish_calls) == 1


class TestAdvisoryLockBusy:
    async def test_lock_busy_marks_row_failed_and_never_runs_jobs(self):
        run_repo = FakeBackupRunRepo(lock_available=False)
        use_case, _, jobs = build(run_repo=run_repo)

        await use_case.execute(now=NOW)

        assert jobs.db_ran is False
        assert jobs.files_ran is False
        (call,) = run_repo.finish_calls
        _run_id, status, _db_key, _files_key, error = call
        assert status == BackupRunStatus.FAILED
        assert error == "another backup is running"


class TestStaleRunningCleanup:
    """Fix 2: RunDueBackup.execute must self-heal a dead worker's leftover
    `running` row every tick, before anything else."""

    async def test_mark_stale_failed_is_called_first_with_the_right_cutoff(self):
        use_case, run_repo, _jobs = build()

        await use_case.execute(now=NOW)

        assert run_repo.mark_stale_failed_calls == [NOW - STALE_AFTER]

    async def test_mark_stale_failed_runs_even_when_backup_is_disabled(self):
        use_case, run_repo, _jobs = build(storage=make_storage(backup_enabled=False))

        await use_case.execute(now=NOW)

        assert len(run_repo.mark_stale_failed_calls) == 1

    async def test_mark_stale_failed_runs_even_when_nothing_is_due(self):
        use_case, run_repo, _jobs = build(due=None)

        await use_case.execute(now=NOW)

        assert len(run_repo.mark_stale_failed_calls) == 1

    async def test_logs_a_warning_when_it_fixed_something(self, glados_caplog):
        run_repo = FakeBackupRunRepo(stale_fixed_count=2)
        use_case, _, _ = build(run_repo=run_repo)

        await use_case.execute(now=NOW)

        warnings = [r for r in glados_caplog.records if r.levelno == logging.WARNING]
        assert warnings
        assert "2" in warnings[0].getMessage()

    async def test_no_warning_when_nothing_was_stale(self, glados_caplog):
        use_case, _run_repo, _jobs = build()  # default stale_fixed_count=0

        await use_case.execute(now=NOW)

        assert [r for r in glados_caplog.records if r.levelno == logging.WARNING] == []


async def test_execute_defaults_now_to_the_current_time_when_omitted():
    """execute(now=None) must still work: BackupScheduler's real tick calls
    it with no argument. The fake cron_schedule ignores whatever `now` it is
    given and always returns DUE, so this only proves the call itself
    doesn't require the argument (the real "what counts as due" arithmetic
    is test_cron_schedule.py's job)."""
    use_case, _run_repo, jobs = build()

    await use_case.execute()  # no `now` passed

    assert jobs.db_ran is True
