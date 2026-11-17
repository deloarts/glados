"""
The parts of the restore command (src/bootstrap/cli/restore.py) that need no
Postgres: reading plain and encrypted archives, the settings filter for an
older server, database naming, and the command line's failure exit. The
restore itself runs against Postgres in tests/pg/test_backup_restore_drill.py.
"""

import gzip

import pytest

from src.bootstrap.cli import restore
from src.bootstrap.cli.restore import RestoreError
from src.bootstrap.cli.restore import adapt_to_server
from src.bootstrap.cli.restore import iter_sql
from src.bootstrap.cli.restore import target_database
from src.modules.platform.infrastructure.security.backup_cipher import encrypt_archive

SQL = b"SET statement_timeout = 0;\nCREATE TABLE t (id int);\n" * 50
KEY = "a-backup-key"


def _sql(path, key=None) -> bytes:
    return b"".join(iter_sql(path, key))


class TestIterSql:
    def test_reads_a_plain_archive(self, tmp_path):
        path = tmp_path / "a.sql.gz"
        path.write_bytes(gzip.compress(SQL))

        assert _sql(path) == SQL

    def test_reads_an_encrypted_archive_whatever_its_name(self, tmp_path):
        path = tmp_path / "renamed.bin"
        path.write_bytes(encrypt_archive(gzip.compress(SQL), KEY))

        assert _sql(path, KEY) == SQL

    def test_an_encrypted_archive_without_a_key_names_the_variable(self, tmp_path):
        path = tmp_path / "a.sql.gz.enc"
        path.write_bytes(encrypt_archive(gzip.compress(SQL), KEY))

        with pytest.raises(RestoreError, match="SECURITY__BACKUP_ENCRYPTION_KEY is not set"):
            _sql(path)

    def test_the_wrong_key_is_named_as_such(self, tmp_path):
        path = tmp_path / "a.sql.gz.enc"
        path.write_bytes(encrypt_archive(gzip.compress(SQL), KEY))

        with pytest.raises(RestoreError, match="different SECURITY__BACKUP_ENCRYPTION_KEY"):
            _sql(path, "another-key")

    def test_a_truncated_plain_archive_is_refused(self, tmp_path):
        path = tmp_path / "a.sql.gz"
        path.write_bytes(gzip.compress(SQL)[:-20])

        with pytest.raises(RestoreError, match="truncated"):
            _sql(path)

    def test_a_file_that_is_no_archive_is_refused(self, tmp_path):
        path = tmp_path / "dump.sql"
        path.write_bytes(SQL)

        with pytest.raises(RestoreError, match="not a Glados backup archive"):
            _sql(path)

    def test_a_missing_file_is_refused(self, tmp_path):
        with pytest.raises(RestoreError, match="Cannot open"):
            _sql(tmp_path / "missing.sql.gz")


class TestAdaptToServer:
    PREAMBLE = b"SET lock_timeout = 0;\nSET transaction_timeout = 0;\nSET x = 1;\n"

    def test_drops_transaction_timeout_for_a_server_before_17(self):
        out = b"".join(adapt_to_server(iter([self.PREAMBLE, b"CREATE TABLE t ();\n"]), 160004))

        assert b"transaction_timeout" not in out
        assert out == b"SET lock_timeout = 0;\nSET x = 1;\nCREATE TABLE t ();\n"

    def test_keeps_everything_for_a_server_from_17(self):
        chunks = [self.PREAMBLE, b"CREATE TABLE t ();\n"]

        assert b"".join(adapt_to_server(iter(chunks), 170002)) == b"".join(chunks)

    def test_passes_large_input_through_unchanged_after_the_preamble(self):
        body = [b"x" * 40_000 for _ in range(5)]

        out = b"".join(adapt_to_server(iter([self.PREAMBLE, *body]), 160004))

        assert out == self.PREAMBLE.replace(b"SET transaction_timeout = 0;\n", b"") + b"".join(body)


class TestNames:
    def test_target_database_reads_the_url(self):
        assert target_database("postgresql+psycopg://u:p@db:5432/glados") == "glados"

    def test_a_sqlite_url_is_refused(self):
        with pytest.raises(RestoreError, match="Postgres"):
            target_database("sqlite:///x.db")

    def test_a_suffixed_name_stays_within_the_identifier_limit(self):
        name = restore._suffixed("g" * 70, "_pre_restore_20260101000000")

        assert len(name.encode()) == 63
        assert name.endswith("_pre_restore_20260101000000")


class TestCommandLine:
    def test_a_missing_file_exits_1_with_a_failure_line(self, tmp_path, capsys):
        with pytest.raises(SystemExit) as exited:
            restore.main(["--file", str(tmp_path / "missing.sql.gz")])

        assert exited.value.code == 1
        err = capsys.readouterr().err
        assert "is no file" in err
        assert "Database restore FAILED." in err

    def test_backup_and_file_exclude_each_other(self, capsys):
        with pytest.raises(SystemExit) as exited:
            restore.main(["--backup", "k", "--file", "f"])

        assert exited.value.code == 2


class _FakeAdmin:
    class info:  # psycopg names the attribute so
        server_version = 160004

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class TestCleanup:
    """Which scratch database a failure drops, with every database call
    replaced; tests/pg/test_backup_restore_drill.py runs the real thing."""

    @pytest.fixture
    def calls(self, tmp_path, monkeypatch):
        dropped: list[str] = []
        monkeypatch.setattr(restore, "_connect", lambda url, database: _FakeAdmin())
        monkeypatch.setattr(restore, "_free_name", lambda admin, base: base)
        monkeypatch.setattr(restore, "_create_database", lambda admin, name, like: None)
        monkeypatch.setattr(restore, "_load", lambda url, database, chunks: list(chunks))
        monkeypatch.setattr(restore, "_verify", lambda url, database: "rev1")
        monkeypatch.setattr(restore, "_drop_database", lambda admin, name: dropped.append(name))
        path = tmp_path / "a.sql.gz"
        path.write_bytes(gzip.compress(SQL))
        return path, dropped

    def _restore(self, path):
        return restore.restore_archive(
            path, "postgresql+psycopg://u:p@db/glados", None, stamp="20260101000000"
        )

    def test_a_failed_load_drops_the_scratch_database(self, calls, monkeypatch):
        path, dropped = calls

        def failing_load(url, database, chunks):
            raise RestoreError("psql stopped")

        monkeypatch.setattr(restore, "_load", failing_load)

        with pytest.raises(RestoreError, match="psql stopped"):
            self._restore(path)

        assert dropped == ["glados_restore_20260101000000"]

    def test_a_stuck_swap_keeps_the_restored_database(self, calls, monkeypatch):
        path, dropped = calls

        def stuck(admin, target, restored, stamp):
            raise restore._SwapStuckError("rename by hand")

        monkeypatch.setattr(restore, "_swap", stuck)

        with pytest.raises(RestoreError, match="rename by hand"):
            self._restore(path)

        assert dropped == []

    def test_a_finished_swap_reports_the_kept_database(self, calls, monkeypatch):
        path, dropped = calls
        monkeypatch.setattr(
            restore, "_swap", lambda admin, target, restored, stamp: "glados_pre_restore_x"
        )

        outcome = self._restore(path)

        assert outcome.previous == "glados_pre_restore_x"
        assert outcome.revision == "rev1"
        assert dropped == []
