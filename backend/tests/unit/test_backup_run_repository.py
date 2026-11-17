"""
Unit tests for SqlAlchemyBackupRunRepository against a real in-memory
SQLite session (same style as test_event_outbox.py's sqlite_session_factory
fixture): try_claim's exactly-once behaviour is a claim about SQLAlchemy's
`ON CONFLICT (slot) DO NOTHING` compiling and running correctly on SQLite,
not something a fake session could prove. run_lock's SQLite bypass mirrors
advisory_lock()'s (see test_advisory_lock.py), verified the same way.
"""

from datetime import UTC
from datetime import datetime
from datetime import timedelta

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import StaticPool

from src.modules.platform.adapters.outbound.persistence.models.backup_run_model import (
    BackupRunOrmModel,
)
from src.modules.platform.adapters.outbound.persistence.models.base import Base
from src.modules.platform.adapters.outbound.persistence.repositories.backup_run_repository import (
    SqlAlchemyBackupRunRepository,
)
from src.modules.platform.domain.value_objects.backup_run_status import BackupRunStatus
from src.modules.platform.domain.value_objects.backup_run_status import BackupRunTrigger
from src.modules.platform.ports.outbound.repositories.backup_run_repository import STALE_AFTER

SLOT = datetime(2026, 8, 28, 2, 0, 0, tzinfo=UTC)


def _aware(dt: datetime) -> datetime:
    """SQLite has no native tz-aware datetime type, so a DateTime(timezone=
    True) column round-trips as naive there (Postgres, timestamptz, does
    not have this quirk). Every write in this repository is UTC, so
    reattaching UTC is safe and keeps assertions dialect-independent."""
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=UTC)


@pytest.fixture
async def session_factory():
    # StaticPool keeps one shared connection, so every session sees the same
    # in-memory database.
    engine = create_async_engine("sqlite+aiosqlite://", poolclass=StaticPool)
    async with engine.begin() as conn:
        await conn.run_sync(
            lambda sync_conn: Base.metadata.create_all(
                sync_conn, tables=[BackupRunOrmModel.__table__]
            )
        )
    try:
        yield async_sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    finally:
        await engine.dispose()


class TestTryClaim:
    async def test_first_claim_for_a_slot_returns_a_running_row(self, session_factory):
        async with session_factory() as db:
            run = await SqlAlchemyBackupRunRepository(db).try_claim(
                SLOT, BackupRunTrigger.SCHEDULED, "host-1"
            )

        assert run is not None
        assert _aware(run.slot) == SLOT
        assert run.trigger == BackupRunTrigger.SCHEDULED
        assert run.status == BackupRunStatus.RUNNING
        assert run.worker == "host-1"
        assert run.id > 0
        assert run.public_id is not None  # Base's Python-side default applied

    async def test_second_claim_for_the_same_slot_returns_none(self, session_factory):
        async with session_factory() as db:
            repo = SqlAlchemyBackupRunRepository(db)
            first = await repo.try_claim(SLOT, BackupRunTrigger.SCHEDULED, "host-1")
            second = await repo.try_claim(SLOT, BackupRunTrigger.SCHEDULED, "host-2")

        assert first is not None
        assert second is None

    async def test_second_claim_from_a_fresh_session_also_returns_none(self, session_factory):
        """The real cross-process scenario: two different gunicorn workers,
        two different sessions, racing for the same due slot."""
        async with session_factory() as db1:
            await SqlAlchemyBackupRunRepository(db1).try_claim(
                SLOT, BackupRunTrigger.SCHEDULED, "host-1"
            )
            # The claiming use case commits the claim through its unit of work.
            await db1.commit()

        async with session_factory() as db2:
            second = await SqlAlchemyBackupRunRepository(db2).try_claim(
                SLOT, BackupRunTrigger.SCHEDULED, "host-2"
            )

        assert second is None

    async def test_different_slots_both_claim_successfully(self, session_factory):
        async with session_factory() as db:
            repo = SqlAlchemyBackupRunRepository(db)
            first = await repo.try_claim(SLOT, BackupRunTrigger.SCHEDULED, "host-1")
            other_slot = datetime(2026, 8, 29, 2, 0, 0, tzinfo=UTC)
            second = await repo.try_claim(other_slot, BackupRunTrigger.SCHEDULED, "host-1")

        assert first is not None
        assert second is not None
        assert first.id != second.id


class TestRunLock:
    async def test_always_true_on_sqlite(self, session_factory):
        async with (
            session_factory() as db,
            SqlAlchemyBackupRunRepository(db).run_lock() as locked,
        ):
            assert locked is True


class TestFinish:
    async def test_finish_updates_status_and_keys(self, session_factory):
        async with session_factory() as db:
            repo = SqlAlchemyBackupRunRepository(db)
            run = await repo.try_claim(SLOT, BackupRunTrigger.SCHEDULED, "host-1")
            assert run is not None
            await repo.finish(
                run.id,
                status=BackupRunStatus.SUCCESS,
                db_key="backups/db/x.sql.gz",
                files_key="backups/files/x/",
                error=None,
            )
            (reloaded,) = await repo.latest(10)

        assert reloaded.status == BackupRunStatus.SUCCESS
        assert reloaded.db_key == "backups/db/x.sql.gz"
        assert reloaded.files_key == "backups/files/x/"
        assert reloaded.finished_at is not None

    async def test_finish_on_an_unknown_id_is_a_no_op(self, session_factory):
        async with session_factory() as db:
            repo = SqlAlchemyBackupRunRepository(db)
            await repo.finish(
                999, status=BackupRunStatus.FAILED, db_key=None, files_key=None, error="x"
            )  # must not raise

            assert await repo.latest(10) == []


class TestQueries:
    async def test_latest_orders_newest_first(self, session_factory):
        async with session_factory() as db:
            repo = SqlAlchemyBackupRunRepository(db)
            await repo.try_claim(SLOT, BackupRunTrigger.SCHEDULED, "host-1")
            later_slot = datetime(2026, 8, 29, 2, 0, 0, tzinfo=UTC)
            await repo.try_claim(later_slot, BackupRunTrigger.SCHEDULED, "host-1")
            runs = await repo.latest(10)

        assert [_aware(r.slot) for r in runs] == [later_slot, SLOT]

    async def test_latest_respects_limit(self, session_factory):
        async with session_factory() as db:
            repo = SqlAlchemyBackupRunRepository(db)
            for day in range(1, 6):
                await repo.try_claim(
                    datetime(2026, 8, day, 2, 0, 0, tzinfo=UTC),
                    BackupRunTrigger.SCHEDULED,
                    "host-1",
                )
            runs = await repo.latest(2)

        assert len(runs) == 2

    async def test_is_running_true_only_while_a_row_is_running(self, session_factory):
        async with session_factory() as db:
            repo = SqlAlchemyBackupRunRepository(db)
            assert await repo.is_running() is False
            run = await repo.try_claim(SLOT, BackupRunTrigger.SCHEDULED, "host-1")
            assert run is not None
            assert await repo.is_running() is True
            await repo.finish(
                run.id,
                status=BackupRunStatus.SUCCESS,
                db_key=None,
                files_key=None,
                error=None,
            )
            assert await repo.is_running() is False

    async def test_last_success_and_last_failure(self, session_factory):
        async with session_factory() as db:
            repo = SqlAlchemyBackupRunRepository(db)
            ok = await repo.try_claim(SLOT, BackupRunTrigger.SCHEDULED, "host-1")
            failed_slot = datetime(2026, 8, 29, 2, 0, 0, tzinfo=UTC)
            bad = await repo.try_claim(failed_slot, BackupRunTrigger.SCHEDULED, "host-1")
            assert ok is not None and bad is not None
            await repo.finish(
                ok.id, status=BackupRunStatus.SUCCESS, db_key="k", files_key="f", error=None
            )
            await repo.finish(
                bad.id,
                status=BackupRunStatus.FAILED,
                db_key=None,
                files_key=None,
                error="boom",
            )

            success = await repo.last_success()
            failure = await repo.last_failure()

        assert success is not None and success.id == ok.id
        assert failure is not None and failure.id == bad.id

    async def test_last_success_is_none_when_nothing_ever_succeeded(self, session_factory):
        async with session_factory() as db:
            assert await SqlAlchemyBackupRunRepository(db).last_success() is None


class TestStaleRunningRows:
    """Fix 2: a `running` row a dead worker never finished must not read as
    in-progress forever, and must eventually be cleaned up. STALE_AFTER (a
    port-level constant, 2h) governs both is_running() and
    mark_stale_failed(); see backup_run_repository.py (the port)."""

    async def test_is_running_ignores_a_stale_running_row(self, session_factory):
        async with session_factory() as db:
            repo = SqlAlchemyBackupRunRepository(db)
            run = await repo.try_claim(SLOT, BackupRunTrigger.SCHEDULED, "host-1")
            assert run is not None
            orm = await db.get(BackupRunOrmModel, run.id)
            orm.started_at = datetime.now(UTC) - STALE_AFTER - timedelta(minutes=1)
            await db.commit()

            assert await repo.is_running() is False

    async def test_is_running_true_for_a_running_row_within_the_window(self, session_factory):
        async with session_factory() as db:
            repo = SqlAlchemyBackupRunRepository(db)
            run = await repo.try_claim(SLOT, BackupRunTrigger.SCHEDULED, "host-1")
            assert run is not None
            orm = await db.get(BackupRunOrmModel, run.id)
            orm.started_at = datetime.now(UTC) - STALE_AFTER + timedelta(minutes=1)
            await db.commit()

            assert await repo.is_running() is True

    async def test_mark_stale_failed_fixes_only_old_running_rows(self, session_factory):
        async with session_factory() as db:
            repo = SqlAlchemyBackupRunRepository(db)
            stale = await repo.try_claim(SLOT, BackupRunTrigger.SCHEDULED, "host-1")
            fresh_slot = datetime(2026, 8, 29, 2, 0, 0, tzinfo=UTC)
            fresh = await repo.try_claim(fresh_slot, BackupRunTrigger.SCHEDULED, "host-1")
            assert stale is not None
            assert fresh is not None

            orm = await db.get(BackupRunOrmModel, stale.id)
            orm.started_at = datetime.now(UTC) - timedelta(hours=3)
            await db.commit()

            fixed_count = await repo.mark_stale_failed(
                older_than=datetime.now(UTC) - timedelta(hours=2)
            )

            reloaded_stale = await db.get(BackupRunOrmModel, stale.id)
            reloaded_fresh = await db.get(BackupRunOrmModel, fresh.id)

        assert fixed_count == 1
        assert reloaded_stale.status == BackupRunStatus.FAILED
        assert reloaded_stale.error == "worker died or timed out"
        assert reloaded_stale.finished_at is not None
        assert reloaded_fresh.status == BackupRunStatus.RUNNING  # untouched

    async def test_mark_stale_failed_returns_zero_when_nothing_is_stale(self, session_factory):
        async with session_factory() as db:
            repo = SqlAlchemyBackupRunRepository(db)
            await repo.try_claim(SLOT, BackupRunTrigger.SCHEDULED, "host-1")

            fixed_count = await repo.mark_stale_failed(
                older_than=datetime.now(UTC) - timedelta(hours=2)
            )

        assert fixed_count == 0

    async def test_mark_stale_failed_ignores_already_terminal_rows(self, session_factory):
        async with session_factory() as db:
            repo = SqlAlchemyBackupRunRepository(db)
            run = await repo.try_claim(SLOT, BackupRunTrigger.SCHEDULED, "host-1")
            assert run is not None
            await repo.finish(
                run.id,
                status=BackupRunStatus.SUCCESS,
                db_key="k",
                files_key="f",
                error=None,
            )
            orm = await db.get(BackupRunOrmModel, run.id)
            orm.started_at = datetime.now(UTC) - timedelta(hours=3)
            await db.commit()

            fixed_count = await repo.mark_stale_failed(
                older_than=datetime.now(UTC) - timedelta(hours=2)
            )
            reloaded = await db.get(BackupRunOrmModel, run.id)

        assert fixed_count == 0
        assert reloaded.status == BackupRunStatus.SUCCESS  # not clobbered
