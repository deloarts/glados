"""
Unit tests for RunClaimedBackup directly (in addition to the coverage it
gets indirectly through test_run_due_backup.py's DUE-slot tests): this
class is also called straight from the run-now endpoint's background task,
so its own `execute(run_id)` contract (lock check, job calls, finish
bookkeeping) gets focused, isolated coverage here.
"""

from contextlib import asynccontextmanager

from src.modules.platform.application.use_cases.backup.run_claimed_backup import RunClaimedBackup
from src.modules.platform.domain.value_objects.backup_run_status import BackupRunStatus
from tests.unit.fakes import FakeUnitOfWork


class FakeRunRepo:
    def __init__(self, *, lock_available: bool = True) -> None:
        self.lock_available = lock_available
        self.finish_calls: list[tuple[int, str, str | None, str | None, str | None]] = []

    @asynccontextmanager
    async def run_lock(self):
        yield self.lock_available

    async def finish(self, run_id, status, db_key, files_key, error) -> None:
        self.finish_calls.append((run_id, status, db_key, files_key, error))


class FakeJobs:
    def __init__(self, *, raises: Exception | None = None) -> None:
        self.raises = raises
        self.db_ran = False
        self.files_ran = False

    async def run_db(self) -> str:
        if self.raises:
            raise self.raises
        self.db_ran = True
        return "db-key"

    async def run_files(self) -> str:
        self.files_ran = True
        return "files-key"


class TestSuccess:
    async def test_runs_both_jobs_and_finishes_with_success_and_keys(self):
        run_repo = FakeRunRepo()
        jobs = FakeJobs()

        await RunClaimedBackup(run_repo, jobs, uow=FakeUnitOfWork()).execute(42)

        assert jobs.db_ran is True
        assert jobs.files_ran is True
        assert run_repo.finish_calls == [(42, BackupRunStatus.SUCCESS, "db-key", "files-key", None)]


class FakeNotifier:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    async def execute(self, task_name: str, message: str) -> None:
        self.calls.append((task_name, message))


class TestJobFailure:
    async def test_a_raising_job_finishes_failed_with_the_error_message(self):
        run_repo = FakeRunRepo()
        jobs = FakeJobs(raises=RuntimeError("disk full"))

        await RunClaimedBackup(run_repo, jobs, uow=FakeUnitOfWork()).execute(7)

        (call,) = run_repo.finish_calls
        run_id, status, db_key, files_key, error = call
        assert run_id == 7
        assert status == BackupRunStatus.FAILED
        assert db_key is None
        assert files_key is None
        assert error == "disk full"

    async def test_a_very_long_error_message_is_truncated(self):
        run_repo = FakeRunRepo()
        jobs = FakeJobs(raises=RuntimeError("x" * 1000))

        await RunClaimedBackup(run_repo, jobs, uow=FakeUnitOfWork()).execute(1)

        (call,) = run_repo.finish_calls
        assert call[4] is not None
        assert len(call[4]) <= 500

    async def test_no_notifier_is_the_old_behaviour(self):
        """`notifier` is optional, default None: a RunClaimedBackup without
        one (as in this class's own tests above) still records the failed
        run and does not raise."""
        run_repo = FakeRunRepo()
        jobs = FakeJobs(raises=RuntimeError("disk full"))

        await RunClaimedBackup(run_repo, jobs, notifier=None, uow=FakeUnitOfWork()).execute(
            9
        )  # must not raise

        assert len(run_repo.finish_calls) == 1

    async def test_a_failure_triggers_the_notifier_with_the_stored_message(self):
        run_repo = FakeRunRepo()
        jobs = FakeJobs(raises=RuntimeError("disk full"))
        notifier = FakeNotifier()

        await RunClaimedBackup(run_repo, jobs, notifier=notifier, uow=FakeUnitOfWork()).execute(7)

        assert notifier.calls == [("backup", "disk full")]

    async def test_the_notifier_receives_the_same_truncated_message_as_the_stored_row(self):
        run_repo = FakeRunRepo()
        jobs = FakeJobs(raises=RuntimeError("x" * 1000))
        notifier = FakeNotifier()

        await RunClaimedBackup(run_repo, jobs, notifier=notifier, uow=FakeUnitOfWork()).execute(1)

        (call,) = run_repo.finish_calls
        (notify_call,) = notifier.calls
        assert notify_call == ("backup", call[4])

    async def test_a_lock_busy_failure_does_not_notify(self):
        """ "Another backup is running" is an expected concurrency guard,
        not an operational failure worth alerting on: only the
        jobs-raised branch above does."""
        run_repo = FakeRunRepo(lock_available=False)
        jobs = FakeJobs()
        notifier = FakeNotifier()

        await RunClaimedBackup(run_repo, jobs, notifier=notifier, uow=FakeUnitOfWork()).execute(3)

        assert notifier.calls == []


class TestLockBusy:
    async def test_neither_job_runs_and_row_finishes_failed(self):
        run_repo = FakeRunRepo(lock_available=False)
        jobs = FakeJobs()

        await RunClaimedBackup(run_repo, jobs, uow=FakeUnitOfWork()).execute(3)

        assert jobs.db_ran is False
        assert jobs.files_ran is False
        assert run_repo.finish_calls == [
            (3, BackupRunStatus.FAILED, None, None, "another backup is running")
        ]


class _LoggingRunRepo(FakeRunRepo):
    def __init__(self, log: list[str], *, lock_available: bool = True) -> None:
        super().__init__(lock_available=lock_available)
        self._log = log

    async def finish(self, run_id, status, db_key, files_key, error) -> None:
        self._log.append(f"finish:{status.value}")
        await super().finish(run_id, status, db_key, files_key, error)


class _LoggingJobs(FakeJobs):
    def __init__(self, log: list[str]) -> None:
        super().__init__()
        self._log = log

    async def run_db(self) -> str:
        self._log.append("run_db")
        return await super().run_db()

    async def run_files(self) -> str:
        self._log.append("run_files")
        return await super().run_files()


class _LoggingUow:
    def __init__(self, log: list[str]) -> None:
        self._log = log

    async def commit(self) -> None:
        self._log.append("commit")

    async def rollback(self) -> None:
        self._log.append("rollback")


class TestTransactionBoundary:
    async def test_the_read_transaction_ends_before_the_jobs_run(self):
        """The read transaction commits before the minutes-long jobs start,
        so the server never terminates it as idle, and the outcome is
        recorded and committed in its own short transaction afterwards."""
        log: list[str] = []

        await RunClaimedBackup(
            _LoggingRunRepo(log), _LoggingJobs(log), uow=_LoggingUow(log)
        ).execute(5)

        assert log == [
            "commit",
            "run_db",
            "run_files",
            f"finish:{BackupRunStatus.SUCCESS.value}",
            "commit",
        ]

    async def test_a_lost_lock_commits_nothing_extra(self):
        """Losing the lock runs no job and commits nothing beyond the one
        transaction that marks the claimed row failed."""
        log: list[str] = []

        await RunClaimedBackup(
            _LoggingRunRepo(log, lock_available=False), _LoggingJobs(log), uow=_LoggingUow(log)
        ).execute(5)

        assert log == [f"finish:{BackupRunStatus.FAILED.value}", "commit"]
