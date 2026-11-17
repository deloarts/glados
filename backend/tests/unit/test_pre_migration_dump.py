"""
The decisions of `admin pre-migration-dump` (src/bootstrap/cli/
pre_migration_dump.py) without a database: when it dumps, how it writes and
prunes, and that a failure exits 1 so the entrypoint refuses to migrate. The
dump against a real database runs in tests/pg/test_backup_restore_drill.py.
"""

import stat

import pytest

from src.bootstrap.cli import pre_migration_dump
from src.bootstrap.cli.pre_migration_dump import SchemaState
from src.bootstrap.cli.pre_migration_dump import prune
from src.bootstrap.cli.pre_migration_dump import write_dump
from src.modules.platform.adapters.outbound.external.schedules import database_dump
from src.modules.platform.domain.exceptions import BackupError
from src.modules.platform.infrastructure.config.settings import cfg
from src.modules.platform.infrastructure.security.backup_cipher import is_encrypted_archive


@pytest.fixture
def env(tmp_path, monkeypatch):
    directory = tmp_path / "dumps"
    monkeypatch.setattr(cfg.database, "url", "postgresql+psycopg://u:p@db:5432/glados")
    monkeypatch.setattr(cfg.backup, "pre_migration_dump_dir", str(directory))
    monkeypatch.setattr(cfg.backup, "pre_migration_dump_keep", 3)
    monkeypatch.setattr(cfg.security, "backup_encryption_key", "a-backup-key")
    return directory


def _state(monkeypatch, *, current, heads=("head1",), has_tables=True):
    state = SchemaState(current=frozenset(current), heads=frozenset(heads), has_tables=has_tables)
    monkeypatch.setattr(pre_migration_dump, "schema_state", lambda url: state)


def _dump(monkeypatch, result=b"-- dump\n"):
    calls: list[str] = []

    async def fake_dump(url: str) -> bytes:
        calls.append(url)
        if isinstance(result, Exception):
            raise result
        return result

    monkeypatch.setattr(database_dump, "dump_database", fake_dump)
    return calls


class TestWhenItDumps:
    async def test_no_dump_at_head(self, env, monkeypatch):
        _state(monkeypatch, current=("head1",))
        calls = _dump(monkeypatch)

        assert await pre_migration_dump.run() == 0
        assert calls == []

    async def test_no_dump_for_an_empty_database(self, env, monkeypatch):
        _state(monkeypatch, current=(), has_tables=False)
        calls = _dump(monkeypatch)

        assert await pre_migration_dump.run() == 0
        assert calls == []

    async def test_no_dump_for_sqlite(self, env, monkeypatch):
        monkeypatch.setattr(cfg.database, "url", "sqlite:///x.db")
        calls = _dump(monkeypatch)

        assert await pre_migration_dump.run() == 0
        assert calls == []

    async def test_a_pending_migration_writes_an_encrypted_dump(self, env, monkeypatch):
        _state(monkeypatch, current=("old1",))
        _dump(monkeypatch)

        assert await pre_migration_dump.run() == 0

        (dump,) = list(env.iterdir())
        assert dump.name.endswith("_old1.sql.gz.enc")
        assert is_encrypted_archive(dump.read_bytes())

    async def test_without_a_key_the_dump_is_plain(self, env, monkeypatch):
        monkeypatch.setattr(cfg.security, "backup_encryption_key", None)
        _state(monkeypatch, current=("old1",))
        _dump(monkeypatch)

        assert await pre_migration_dump.run() == 0

        (dump,) = list(env.iterdir())
        assert dump.name.endswith("_old1.sql.gz")


class TestFailures:
    async def test_a_failed_dump_exits_1(self, env, monkeypatch, capsys):
        _state(monkeypatch, current=("old1",))
        _dump(monkeypatch, BackupError("pg_dump failed: disk full"))

        assert await pre_migration_dump.run() == 1
        assert "disk full" in capsys.readouterr().err
        assert not env.exists()

    async def test_an_unreadable_revision_exits_1(self, env, monkeypatch, capsys):
        def broken(url):
            raise RuntimeError("connection refused")

        monkeypatch.setattr(pre_migration_dump, "schema_state", broken)

        assert await pre_migration_dump.run() == 1
        assert "connection refused" in capsys.readouterr().err


class TestFiles:
    def test_write_dump_leaves_only_the_final_owner_only_file(self, tmp_path):
        path = write_dump(tmp_path / "d", "2026-01-01T00-00-00_x.sql.gz", b"data")

        assert [p.name for p in (tmp_path / "d").iterdir()] == [path.name]
        assert path.read_bytes() == b"data"
        assert stat.S_IMODE(path.stat().st_mode) == 0o600
        assert stat.S_IMODE((tmp_path / "d").stat().st_mode) == 0o700

    def test_prune_keeps_the_newest_dumps_and_ignores_other_files(self, tmp_path):
        names = [f"2026-01-0{day}T00-00-00_r.sql.gz" for day in range(1, 6)]
        for name in [*names, "notes.txt"]:
            (tmp_path / name).write_bytes(b"x")

        removed = prune(tmp_path, keep=2)

        assert sorted(p.name for p in removed) == names[:3]
        assert sorted(p.name for p in tmp_path.iterdir()) == sorted([*names[3:], "notes.txt"])

    def test_prune_always_keeps_one(self, tmp_path):
        (tmp_path / "2026-01-01T00-00-00_r.sql.gz").write_bytes(b"x")

        assert prune(tmp_path, keep=0) == []
