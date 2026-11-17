"""
The backup and restore drill on a real Postgres: seed a database, back it
up with the app's own backup job, change the data, restore, and compare
every table's row count with the counts at backup time. It also proves the
failure paths leave the current database exactly as it was, and that the
migration lock in alembic/env.py makes a second migration wait.

Each test works in its own scratch database on the server GLADOS_TEST_PG_URL
names, created and dropped here together with every database the restore
derives from its name, so the shared throwaway database of the race tests
is never renamed. The drill needs pg_dump and psql on the PATH, the same
client tools the backend image ships; CI checks for them before it runs.
"""

from __future__ import annotations

import asyncio
import gzip
import shutil
import threading
import time
import uuid
from collections.abc import Iterator
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy import inspect
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine

from alembic import command
from alembic.config import Config as AlembicConfig
from alembic.script import ScriptDirectory
from src.bootstrap.cli.restore import RestoreError
from src.bootstrap.cli.restore import restore_archive
from src.modules.platform.adapters.outbound.external.schedules.database_schedule import (
    DatabaseBackupJob,
)
from src.modules.platform.adapters.outbound.persistence.advisory_lock import AdvisoryLockKey
from src.modules.platform.domain.entities.admin_settings.storage import AdminStorageSettings
from src.modules.platform.infrastructure.config.settings import cfg

pytestmark = pytest.mark.skipif(
    shutil.which("pg_dump") is None or shutil.which("psql") is None,
    reason="the backup and restore drill needs pg_dump and psql on the PATH",
)

_BACKEND_ROOT = Path(__file__).resolve().parents[2]
_KEY = "drill-backup-encryption-key"
_STAMP = "20260101000000"


def _alembic_config() -> AlembicConfig:
    config = AlembicConfig(str(_BACKEND_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(_BACKEND_ROOT / "alembic"))
    return config


def _head() -> str:
    head = ScriptDirectory.from_config(_alembic_config()).get_current_head()
    assert head is not None
    return head


@pytest.fixture
def drill_url(_postgres: str) -> Iterator[str]:
    """A scratch database with the schema from the models and the head
    revision stamped, as a deployed database has. Dropped afterwards with
    every database whose name starts with its own."""
    from src.modules.platform.adapters.outbound.persistence.models.base import Base
    from tests.pg.conftest import _import_all_models

    name = f"glados_drill_{uuid.uuid4().hex[:8]}"
    admin = create_engine(
        make_url(_postgres).set(database="postgres"), isolation_level="AUTOCOMMIT"
    )
    with admin.connect() as connection:
        connection.execute(text(f'CREATE DATABASE "{name}"'))
    url = make_url(_postgres).set(database=name).render_as_string(hide_password=False)
    try:
        engine = create_engine(url)
        _import_all_models()
        Base.metadata.create_all(engine)
        with engine.begin() as connection:
            connection.execute(
                text("CREATE TABLE alembic_version (version_num VARCHAR(32) PRIMARY KEY)")
            )
            connection.execute(text("INSERT INTO alembic_version VALUES (:v)"), {"v": _head()})
        engine.dispose()
        yield url
    finally:
        with admin.connect() as connection:
            names = connection.execute(
                text("SELECT datname FROM pg_database WHERE datname LIKE :prefix"),
                {"prefix": f"{name}%"},
            ).scalars()
            for leftover in list(names):
                connection.execute(text(f'DROP DATABASE IF EXISTS "{leftover}" WITH (FORCE)'))
        admin.dispose()


def _seed(url: str) -> None:
    from tests.pg._floor import seed
    from tests.pg._race import sessions

    async def run() -> None:
        engine = create_async_engine(url)
        try:
            async with sessions(engine)() as db:
                floor = await seed(db)
                # The floor builds its rows on demand and commits each; these
                # reach a lot, its production orders, an order line and the
                # catalogue, users and settings behind them.
                machine = await floor.machine()
                await floor.running_order()
                await floor.queued_order(4.0, machine_id=machine.id, queue_sequence=2)
                await floor.bought_line(5.0)
                await floor.bought_demand(3.0)
        finally:
            await engine.dispose()

    asyncio.run(run())


def _row_counts(url: str) -> dict[str, int]:
    engine = create_engine(url)
    try:
        with engine.connect() as connection:
            names = inspect(connection).get_table_names(schema="public")
            return {
                name: connection.execute(text(f'SELECT count(*) FROM "{name}"')).scalar_one()
                for name in names
            }
    finally:
        engine.dispose()


def _databases(url: str, prefix: str) -> set[str]:
    engine = create_engine(make_url(url).set(database="postgres"))
    try:
        with engine.connect() as connection:
            return set(
                connection.execute(
                    text("SELECT datname FROM pg_database WHERE datname LIKE :prefix"),
                    {"prefix": f"{prefix}%"},
                ).scalars()
            )
    finally:
        engine.dispose()


def _change_data(url: str) -> None:
    """Changes the data the way a day of use would, so a restore that did
    nothing could not pass the count comparison."""
    engine = create_engine(url)
    try:
        with engine.begin() as connection:
            connection.execute(text("DELETE FROM alembic_version"))
            connection.execute(text("INSERT INTO alembic_version VALUES ('changed')"))
            connection.execute(text("CREATE TABLE drill_extra (id int)"))
            connection.execute(text("INSERT INTO drill_extra VALUES (1), (2)"))
    finally:
        engine.dispose()


def _backup(url: str, storage: Path, key: str | None, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Backs the database up with the app's backup job into local storage
    under `storage` and returns the archive's path."""
    monkeypatch.setattr(cfg.local_storage, "base_dir", str(storage))
    settings = AdminStorageSettings(
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
    job = DatabaseBackupJob(settings, url, encryption_key=key, require_encryption=key is not None)
    return storage / asyncio.run(job.run())


def _name(url: str) -> str:
    database = make_url(url).database
    assert database is not None
    return database


class TestRestoreDrill:
    def test_an_encrypted_backup_replaces_a_running_database(
        self, drill_url, tmp_path, monkeypatch
    ):
        _seed(drill_url)
        at_backup = _row_counts(drill_url)
        archive = _backup(drill_url, tmp_path, _KEY, monkeypatch)
        assert archive.name.endswith(".sql.gz.enc")
        _change_data(drill_url)
        changed = _row_counts(drill_url)

        # A connection left open, as a backend that was not stopped holds.
        engine = create_engine(drill_url)
        leftover = engine.connect()
        leftover.execute(text("SELECT 1"))
        try:
            outcome = restore_archive(archive, drill_url, _KEY, stamp=_STAMP)
        finally:
            leftover.invalidate()
            engine.dispose()

        name = _name(drill_url)
        assert outcome.database == name
        assert outcome.previous == f"{name}_pre_restore_{_STAMP}"
        assert outcome.revision == _head()
        assert _row_counts(drill_url) == at_backup
        assert sum(at_backup.values()) > 20
        previous_url = make_url(drill_url).set(database=outcome.previous)
        assert _row_counts(previous_url.render_as_string(hide_password=False)) == changed
        assert _databases(drill_url, f"{name}_restore_") == set()

    def test_a_plain_archive_still_restores(self, drill_url, tmp_path, monkeypatch):
        _seed(drill_url)
        at_backup = _row_counts(drill_url)
        archive = _backup(drill_url, tmp_path, None, monkeypatch)
        assert archive.name.endswith(".sql.gz")
        _change_data(drill_url)

        restore_archive(archive, drill_url, None, stamp=_STAMP)

        assert _row_counts(drill_url) == at_backup

    def test_a_lost_database_is_restored_from_a_file(self, drill_url, tmp_path, monkeypatch):
        _seed(drill_url)
        at_backup = _row_counts(drill_url)
        archive = _backup(drill_url, tmp_path, _KEY, monkeypatch)
        admin = create_engine(
            make_url(drill_url).set(database="postgres"), isolation_level="AUTOCOMMIT"
        )
        with admin.connect() as connection:
            connection.execute(text(f'DROP DATABASE "{_name(drill_url)}" WITH (FORCE)'))
        admin.dispose()

        outcome = restore_archive(archive, drill_url, _KEY, stamp=_STAMP)

        assert outcome.previous is None
        assert _row_counts(drill_url) == at_backup


class TestRestoreFailures:
    """Every failure ends with an error, the current database as it was and
    no scratch database left behind."""

    @pytest.fixture
    def seeded(self, drill_url, tmp_path, monkeypatch) -> tuple[str, Path, dict[str, int]]:
        _seed(drill_url)
        archive = _backup(drill_url, tmp_path, _KEY, monkeypatch)
        _change_data(drill_url)
        return drill_url, archive, _row_counts(drill_url)

    def _assert_untouched(self, url: str, counts: dict[str, int]) -> None:
        name = _name(url)
        assert _row_counts(url) == counts
        assert _databases(url, name) == {name}

    def test_a_truncated_archive(self, seeded, tmp_path):
        url, archive, counts = seeded
        truncated = tmp_path / "truncated.sql.gz.enc"
        truncated.write_bytes(archive.read_bytes()[:-100])

        with pytest.raises(RestoreError, match=r"truncated|damaged"):
            restore_archive(truncated, url, _KEY, stamp=_STAMP)

        self._assert_untouched(url, counts)

    def test_the_wrong_key(self, seeded):
        url, archive, counts = seeded

        with pytest.raises(RestoreError, match="different SECURITY__BACKUP_ENCRYPTION_KEY"):
            restore_archive(archive, url, "another-key", stamp=_STAMP)

        self._assert_untouched(url, counts)

    def test_sql_that_fails_halfway(self, seeded, tmp_path):
        url, _archive, counts = seeded
        broken = tmp_path / "broken.sql.gz"
        broken.write_bytes(
            gzip.compress(b"CREATE TABLE half (id int);\nINSERT INTO missing VALUES (1);\n")
        )

        with pytest.raises(RestoreError, match="psql stopped"):
            restore_archive(broken, url, None, stamp=_STAMP)

        self._assert_untouched(url, counts)

    def test_an_archive_that_is_no_glados_database(self, seeded, tmp_path):
        url, _archive, counts = seeded
        foreign = tmp_path / "foreign.sql.gz"
        foreign.write_bytes(gzip.compress(b"CREATE TABLE foreign_data (id int);\n"))

        with pytest.raises(RestoreError, match="alembic_version"):
            restore_archive(foreign, url, None, stamp=_STAMP)

        self._assert_untouched(url, counts)


class TestMigrationLock:
    def test_a_second_migration_waits_for_the_lock(self, drill_url):
        key = int(AdvisoryLockKey.MIGRATION)
        engine = create_engine(drill_url)
        holder = engine.connect()
        holder.begin()
        holder.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": key})
        failures: list[BaseException] = []

        def migrate() -> None:
            try:
                with engine.connect() as connection:
                    config = _alembic_config()
                    config.attributes["connection"] = connection
                    command.upgrade(config, "head")
                    connection.commit()
            except BaseException as exc:
                failures.append(exc)

        worker = threading.Thread(target=migrate)
        worker.start()
        try:
            deadline = time.monotonic() + 10
            waiting = 0
            while time.monotonic() < deadline and not waiting:
                with engine.connect() as watcher:
                    waiting = watcher.execute(
                        text(
                            "SELECT count(*) FROM pg_locks WHERE locktype = 'advisory' "
                            "AND NOT granted AND objid = :key"
                        ),
                        {"key": key},
                    ).scalar_one()
                time.sleep(0.05)
            assert waiting == 1
            assert worker.is_alive()
        finally:
            holder.rollback()
            holder.close()
            worker.join(timeout=30)
            engine.dispose()

        assert not worker.is_alive()
        assert failures == []


class TestPreMigrationDump:
    """`admin pre-migration-dump` against a real database: no dump while the
    revision matches the image's head, a restorable dump once it differs."""

    @pytest.fixture
    def dump_dir(self, drill_url, tmp_path, monkeypatch) -> Path:
        directory = tmp_path / "pre-migration-dumps"
        monkeypatch.setattr(cfg.database, "url", drill_url)
        monkeypatch.setattr(cfg.backup, "pre_migration_dump_dir", str(directory))
        monkeypatch.setattr(cfg.backup, "pre_migration_dump_keep", 2)
        monkeypatch.setattr(cfg.security, "backup_encryption_key", _KEY)
        return directory

    def _set_revision(self, url: str, revision: str) -> None:
        engine = create_engine(url)
        try:
            with engine.begin() as connection:
                connection.execute(
                    text("UPDATE alembic_version SET version_num = :v"), {"v": revision}
                )
        finally:
            engine.dispose()

    def test_no_dump_while_the_database_is_at_head(self, dump_dir):
        from src.bootstrap.cli.pre_migration_dump import run

        assert asyncio.run(run()) == 0
        assert not dump_dir.exists()

    def test_a_pending_migration_gets_a_restorable_dump(self, drill_url, dump_dir):
        from src.bootstrap.cli.pre_migration_dump import run

        _seed(drill_url)
        self._set_revision(drill_url, "older0revision")
        at_dump = _row_counts(drill_url)

        assert asyncio.run(run()) == 0

        (dump,) = list(dump_dir.iterdir())
        assert dump.name.endswith("_older0revision.sql.gz.enc")
        _change_data(drill_url)
        restore_archive(dump, drill_url, _KEY, stamp=_STAMP)
        assert _row_counts(drill_url) == at_dump

    def test_only_the_newest_dumps_are_kept(self, drill_url, dump_dir):
        from src.bootstrap.cli.pre_migration_dump import run

        self._set_revision(drill_url, "older0revision")
        dump_dir.mkdir()
        for stale in ("2020-01-01T00-00-00_a.sql.gz", "2020-01-02T00-00-00_b.sql.gz.enc"):
            (dump_dir / stale).write_bytes(b"old")

        assert asyncio.run(run()) == 0

        names = sorted(path.name for path in dump_dir.iterdir())
        assert len(names) == 2
        assert names[0] == "2020-01-02T00-00-00_b.sql.gz.enc"
