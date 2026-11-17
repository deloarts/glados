"""
Integration coverage for backup_runs run record:
  - RunDueBackup's exactly-once claim against the *real* schema
    (Base.metadata.create_all via tests/integration/conftest.py's `_schema`
    fixture, not the single-table engine test_backup_run_repository.py's
    unit tests use).
  - POST .../run-now: 202 when nothing is running, 409 (BackupAlreadyRunning
    Error, mapped in exception_handlers) while a row already is.
  - GET .../storage/backups includes last_run/runs.

TestClient runs FastAPI BackgroundTasks synchronously before `.post()`
returns (verified empirically), so by the time a run-now response comes
back, its background job has already finished. That job runs conftest's
FakeBackupJobs, never a real pg_dump: see `_no_real_backup_jobs` there for
why a real one hangs the suite outright. The 409 case is arranged directly
through the repository rather than by racing two real requests.
"""

from datetime import UTC
from datetime import datetime
from datetime import timedelta

from sqlalchemy.orm import Session

from src.bootstrap.adapters.outbound.persistence.repositories.admin_settings_repository import (
    SqlAlchemyAdminSettingsRepository,
)
from src.modules.platform.adapters.outbound.persistence.models.backup_run_model import (
    BackupRunOrmModel,
)
from src.modules.platform.adapters.outbound.persistence.repositories.backup_run_repository import (
    SqlAlchemyBackupRunRepository,
)
from src.modules.platform.adapters.outbound.persistence.session import SessionLocal
from src.modules.platform.adapters.outbound.persistence.unit_of_work import SqlAlchemyUnitOfWork
from src.modules.platform.application.use_cases.backup.run_due_backup import RunDueBackup
from src.modules.platform.domain.value_objects.backup_run_status import BackupRunStatus
from src.modules.platform.domain.value_objects.backup_run_status import BackupRunTrigger
from src.modules.platform.domain.value_objects.permission import Permission

BASE = "/api/v1/web/admin/settings"


async def _configure_backup(db: Session) -> None:
    repo = SqlAlchemyAdminSettingsRepository(db)
    settings = await repo.get_storage()
    settings.backup_enabled = True
    settings.backup_path = "backups"
    settings.backup_cron = "0 2 * * *"
    settings.backup_retention_count = 7
    await repo.save_storage(settings)
    await db.commit()


class FakeCronSchedule:
    def __init__(self, due: datetime | None) -> None:
        self.due = due

    def latest_due(self, cron, now, grace):
        return self.due


class FakeJobs:
    def __init__(self) -> None:
        self.runs = 0

    async def run_db(self) -> str:
        self.runs += 1
        return "backups/db/x.sql.gz"

    async def run_files(self) -> str:
        return "backups/files/x/"


class TestRunDueBackupExactlyOnce:
    async def test_two_executions_for_the_same_slot_claim_and_run_once(self, db: Session):
        await _configure_backup(db)
        due = datetime(2026, 8, 28, 2, 0, 0, tzinfo=UTC)
        jobs = FakeJobs()

        async def tick() -> None:
            await RunDueBackup(
                settings_repo=SqlAlchemyAdminSettingsRepository(db),
                run_repo=SqlAlchemyBackupRunRepository(db),
                uow=SqlAlchemyUnitOfWork(db),
                jobs_factory=lambda _settings: jobs,
                cron_schedule=FakeCronSchedule(due),
                worker="test-worker",
            ).execute(now=due)

        await tick()  # worker A's tick
        await tick()  # worker B's tick, same due slot -> must see the claim taken

        rows = await SqlAlchemyBackupRunRepository(db).latest(10)
        assert len(rows) == 1
        assert rows[0].trigger == BackupRunTrigger.SCHEDULED
        assert rows[0].status == BackupRunStatus.SUCCESS
        assert jobs.runs == 1  # the job body itself ran exactly once

    async def test_a_tick_persists_the_stale_cleanup_the_claim_and_the_outcome(self, db: Session):
        """Read back from a fresh session, so a tick that forgets to commit
        its unit of work fails here."""
        await _configure_backup(db)
        stale = await SqlAlchemyBackupRunRepository(db).try_claim(
            datetime(2026, 8, 27, 2, 0, 0, tzinfo=UTC), BackupRunTrigger.SCHEDULED, "dead"
        )
        assert stale is not None
        due = datetime(2026, 8, 28, 2, 0, 0, tzinfo=UTC)
        orm = await db.get(BackupRunOrmModel, stale.id)
        orm.started_at = due - timedelta(hours=3)
        await db.commit()

        await RunDueBackup(
            settings_repo=SqlAlchemyAdminSettingsRepository(db),
            run_repo=SqlAlchemyBackupRunRepository(db),
            uow=SqlAlchemyUnitOfWork(db),
            jobs_factory=lambda _settings: FakeJobs(),
            cron_schedule=FakeCronSchedule(due),
            worker="test-worker",
        ).execute(now=due)

        async with SessionLocal() as fresh:
            rows = await SqlAlchemyBackupRunRepository(fresh).latest(10)
        by_worker = {row.worker: row.status for row in rows}
        assert by_worker == {
            "dead": BackupRunStatus.FAILED,
            "test-worker": BackupRunStatus.SUCCESS,
        }

    async def test_a_tick_with_nothing_due_persists_the_stale_cleanup(self, db: Session):
        await _configure_backup(db)
        stale = await SqlAlchemyBackupRunRepository(db).try_claim(
            datetime(2026, 8, 27, 2, 0, 0, tzinfo=UTC), BackupRunTrigger.SCHEDULED, "dead"
        )
        assert stale is not None
        orm = await db.get(BackupRunOrmModel, stale.id)
        orm.started_at = datetime.now(UTC) - timedelta(hours=3)
        await db.commit()

        await RunDueBackup(
            settings_repo=SqlAlchemyAdminSettingsRepository(db),
            run_repo=SqlAlchemyBackupRunRepository(db),
            uow=SqlAlchemyUnitOfWork(db),
            jobs_factory=lambda _settings: FakeJobs(),
            cron_schedule=FakeCronSchedule(due=None),
            worker="test-worker",
        ).execute()

        async with SessionLocal() as fresh:
            (row,) = await SqlAlchemyBackupRunRepository(fresh).latest(10)
        assert row.status == BackupRunStatus.FAILED


class TestRunNowEndpoint:
    async def test_returns_202_and_records_a_manual_run(self, auth_client, db: Session):
        await _configure_backup(db)
        client = await auth_client(permissions=[Permission.WRITE_SETTINGS])

        response = await client.post(f"{BASE}/storage/backups/run-now")

        assert response.status_code == 202
        rows = await SqlAlchemyBackupRunRepository(db).latest(10)
        assert len(rows) == 1
        assert rows[0].trigger == BackupRunTrigger.MANUAL
        # RunClaimedBackup always finishes the row, never leaves it "running".
        assert rows[0].status == BackupRunStatus.SUCCESS

    async def test_returns_409_while_a_run_is_already_in_progress(self, auth_client, db: Session):
        await _configure_backup(db)
        await SqlAlchemyBackupRunRepository(db).try_claim(
            datetime.now(UTC), BackupRunTrigger.SCHEDULED, "other-worker"
        )
        client = await auth_client(permissions=[Permission.WRITE_SETTINGS])

        response = await client.post(f"{BASE}/storage/backups/run-now")

        assert response.status_code == 409
        # The 409 gate fires before any new claim attempt: still one row.
        assert len(await SqlAlchemyBackupRunRepository(db).latest(10)) == 1

    async def test_returns_400_when_backup_is_not_configured(self, auth_client, db: Session):
        # conftest seeds storage with backup_enabled defaulting False.
        client = await auth_client(permissions=[Permission.WRITE_SETTINGS])

        response = await client.post(f"{BASE}/storage/backups/run-now")

        assert response.status_code == 400

    async def test_requires_write_settings(self, auth_client, db: Session):
        await _configure_backup(db)
        client = await auth_client(permissions=[])

        response = await client.post(f"{BASE}/storage/backups/run-now")

        assert response.status_code == 403


class TestStaleRunningRows:
    """Fix 2: a `running` row a dead worker never finished must not block
    run-now (409) forever. Two separate mechanisms cover this, and each
    gets its own test: is_running() itself ignores a row past STALE_AFTER
    (so run-now recovers immediately, with no tick needed at all), and
    RunDueBackup marks such rows `failed` in the DB every tick, even when
    nothing is actually due, so the row's *status* eventually reflects
    reality too, not just future is_running() reads."""

    async def test_run_now_succeeds_when_the_only_running_row_is_stale(
        self, auth_client, db: Session
    ):
        await _configure_backup(db)
        stale_run = await SqlAlchemyBackupRunRepository(db).try_claim(
            datetime(2026, 8, 28, 2, 0, 0, tzinfo=UTC),
            BackupRunTrigger.SCHEDULED,
            "dead-worker",
        )
        assert stale_run is not None
        orm = await db.get(BackupRunOrmModel, stale_run.id)
        orm.started_at = datetime.now(UTC) - timedelta(hours=3)  # older than STALE_AFTER (2h)
        await db.commit()
        client = await auth_client(permissions=[Permission.WRITE_SETTINGS])

        # is_running() filters this row out on its own, no RunDueBackup
        # tick required: contrast with test_returns_409_while_a_run_is_
        # already_in_progress (TestRunNowEndpoint), same setup minus the
        # backdated started_at, which answers 409.
        response = await client.post(f"{BASE}/storage/backups/run-now")

        assert response.status_code == 202
        # The stale row itself is untouched by run-now (only mark_stale_
        # failed, below, updates it). There are now two rows.
        assert len(await SqlAlchemyBackupRunRepository(db).latest(10)) == 2

    async def test_run_due_backup_marks_a_stale_row_failed_even_with_nothing_due(self, db: Session):
        await _configure_backup(db)
        run = await SqlAlchemyBackupRunRepository(db).try_claim(
            datetime(2026, 8, 28, 2, 0, 0, tzinfo=UTC),
            BackupRunTrigger.SCHEDULED,
            "dead-worker",
        )
        assert run is not None
        orm = await db.get(BackupRunOrmModel, run.id)
        orm.started_at = datetime.now(UTC) - timedelta(hours=3)
        await db.commit()

        await RunDueBackup(
            settings_repo=SqlAlchemyAdminSettingsRepository(db),
            run_repo=SqlAlchemyBackupRunRepository(db),
            uow=SqlAlchemyUnitOfWork(db),
            jobs_factory=lambda _settings: FakeJobs(),
            cron_schedule=FakeCronSchedule(due=None),  # nothing scheduled is due right now
            worker="test-worker",
        ).execute()

        reloaded = await db.get(BackupRunOrmModel, run.id)
        assert reloaded.status == BackupRunStatus.FAILED
        assert reloaded.error == "worker died or timed out"


class TestListBackupsRunHistory:
    async def test_includes_last_run_and_runs(self, auth_client, db: Session):
        await _configure_backup(db)
        repo = SqlAlchemyBackupRunRepository(db)
        run = await repo.try_claim(
            datetime(2026, 8, 28, 2, 0, 0, tzinfo=UTC), BackupRunTrigger.SCHEDULED, "w-1"
        )
        assert run is not None
        await repo.finish(
            run.id,
            status=BackupRunStatus.SUCCESS,
            db_key="backups/db/x.sql.gz",
            files_key="backups/files/x/",
            error=None,
        )
        client = await auth_client(permissions=[Permission.WRITE_SETTINGS])

        response = await client.get(f"{BASE}/storage/backups")

        assert response.status_code == 200
        body = response.json()
        assert body["last_run"] is not None
        assert body["last_run"]["status"] == BackupRunStatus.SUCCESS
        assert body["last_run"]["trigger"] == BackupRunTrigger.SCHEDULED
        assert len(body["runs"]) == 1

    async def test_last_run_is_none_when_nothing_ever_ran(self, auth_client, db: Session):
        await _configure_backup(db)
        client = await auth_client(permissions=[Permission.WRITE_SETTINGS])

        response = await client.get(f"{BASE}/storage/backups")

        assert response.status_code == 200
        body = response.json()
        assert body["last_run"] is None
        assert body["runs"] == []


class TestListBackupsWarnings:
    async def test_lists_warnings_and_no_download_urls(self, auth_client, db: Session):
        await _configure_backup(db)
        client = await auth_client(permissions=[Permission.WRITE_SETTINGS])

        response = await client.get(f"{BASE}/storage/backups")

        assert response.status_code == 200
        body = response.json()
        # Enabled now, but still the local provider and no backup key.
        assert body["warnings"] == ["stored_on_host", "encryption_key_missing"]
        assert all("url" not in entry for entry in [*body["db"], *body["files"]])
