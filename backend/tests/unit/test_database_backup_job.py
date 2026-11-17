"""
DatabaseBackupJob (adapters/outbound/external/schedules/database_schedule.py)
with pg_dump replaced: it refuses to run without a backup key unless told
that a plain archive is acceptable, and writes an encrypted archive that
decrypts back to the dump when it has one.
"""

import gzip
import io

import pytest

from src.modules.platform.adapters.outbound.external.schedules import database_schedule
from src.modules.platform.adapters.outbound.external.schedules.database_schedule import (
    DatabaseBackupJob,
)
from src.modules.platform.domain.entities.admin_settings.storage import AdminStorageSettings
from src.modules.platform.domain.exceptions import BackupError
from src.modules.platform.infrastructure.config.settings import cfg
from src.modules.platform.infrastructure.security.backup_cipher import decrypt_stream

DUMP = b"-- PostgreSQL database dump\nCREATE TABLE t (id int);\n"


def _settings() -> AdminStorageSettings:
    return AdminStorageSettings(
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
        backup_retention_count=2,
    )


@pytest.fixture
def storage(tmp_path, monkeypatch):
    calls: list[str] = []

    async def fake_dump(url: str) -> bytes:
        calls.append(url)
        return DUMP

    monkeypatch.setattr(database_schedule, "dump_database", fake_dump)
    monkeypatch.setattr(cfg.local_storage, "base_dir", str(tmp_path))
    return tmp_path, calls


async def test_without_a_key_the_job_refuses_before_dumping(storage):
    _root, calls = storage

    with pytest.raises(BackupError, match="SECURITY__BACKUP_ENCRYPTION_KEY"):
        await DatabaseBackupJob(_settings(), "postgresql://db/glados").run()

    assert calls == []


async def test_with_a_key_the_archive_is_encrypted(storage):
    root, _calls = storage

    key = await DatabaseBackupJob(
        _settings(), "postgresql://db/glados", encryption_key="a-backup-key"
    ).run()

    assert key.startswith("backups/db/") and key.endswith(".sql.gz.enc")
    compressed = b"".join(decrypt_stream(io.BytesIO((root / key).read_bytes()), "a-backup-key"))
    assert gzip.decompress(compressed) == DUMP


async def test_a_plain_archive_only_when_encryption_is_not_required(storage, glados_caplog):
    root, _calls = storage

    key = await DatabaseBackupJob(
        _settings(), "postgresql://db/glados", require_encryption=False
    ).run()

    assert key.endswith(".sql.gz")
    assert gzip.decompress((root / key).read_bytes()) == DUMP
    assert any("unencrypted" in r.getMessage() for r in glados_caplog.records)


async def test_retention_counts_both_formats(storage):
    root, _calls = storage
    db_dir = root / "backups" / "db"
    db_dir.mkdir(parents=True)
    (db_dir / "2020-01-01T00-00-00.sql.gz").write_bytes(b"old")
    (db_dir / "2020-01-02T00-00-00.sql.gz.enc").write_bytes(b"old")

    key = await DatabaseBackupJob(
        _settings(), "postgresql://db/glados", encryption_key="a-backup-key"
    ).run()

    assert sorted(p.name for p in db_dir.iterdir()) == [
        "2020-01-02T00-00-00.sql.gz.enc",
        key.rsplit("/", 1)[-1],
    ]
