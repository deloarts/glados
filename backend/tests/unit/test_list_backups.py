"""
Unit tests for ListBackups: the archives in both formats, the warnings the
backup configuration earns, and no download URL on any entry, since an
archive leaves only through the authenticated download route.
"""

import pytest

from src.modules.platform.application.use_cases.admin_settings.list_backups import ListBackups
from src.modules.platform.domain.entities.admin_settings.storage import AdminStorageSettings
from src.modules.platform.domain.entities.backup_run import BackupRun
from src.modules.platform.domain.exceptions import InsufficientPermissionsError
from src.modules.platform.domain.value_objects.backup_warning import BackupWarning
from src.modules.platform.domain.value_objects.permission import Permission
from tests.factories import make_user


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


class FakeStorage:
    """list_keys returns whatever is configured. get_url fails, so a listing
    that still asked for a presigned URL would fail the test."""

    def __init__(self, db_keys: list[str], file_keys: list[str]) -> None:
        self._db_keys = db_keys
        self._file_keys = file_keys

    async def list_keys(self, prefix: str) -> list[str]:
        if prefix.endswith("/db/"):
            return self._db_keys
        return self._file_keys

    def get_url(self, key: str) -> str:
        raise AssertionError(f"the backup listing asked for a URL of {key!r}")


class FakeRunRepo:
    """No run history recorded yet."""

    async def latest(self, limit: int) -> list[BackupRun]:
        return []


def build_use_case(
    storage_settings: AdminStorageSettings, storage: FakeStorage, *, key: bool = True
) -> ListBackups:
    return ListBackups(
        repo=FakeSettingsRepo(storage_settings),
        storage_factory=lambda settings: storage,
        run_repo=FakeRunRepo(),
        encryption_key_configured=key,
    )


class TestPermission:
    async def test_actor_without_write_settings_is_rejected(self):
        use_case = build_use_case(make_storage(), FakeStorage([], []))

        with pytest.raises(InsufficientPermissionsError):
            await use_case.execute(make_user(permissions=[]))


class TestBackupNotConfigured:
    async def test_backup_disabled_returns_empty_lists(self):
        use_case = build_use_case(
            make_storage(backup_enabled=False), FakeStorage(["backups/db/x.sql.gz"], [])
        )

        result = await use_case.execute(make_user(permissions=[Permission.WRITE_SETTINGS]))

        assert result.db == []
        assert result.files == []


class TestArchives:
    async def test_both_archive_formats_are_listed_newest_first(self):
        keys = [
            "backups/db/2026-07-13T02-00-00.sql.gz",
            "backups/db/2026-07-14T02-00-00.sql.gz.enc",
        ]
        use_case = build_use_case(make_storage(), FakeStorage(keys, []))

        result = await use_case.execute(make_user(permissions=[Permission.WRITE_SETTINGS]))

        assert [(e.key, e.timestamp, e.encrypted) for e in result.db] == [
            (keys[1], "2026-07-14T02:00:00", True),
            (keys[0], "2026-07-13T02:00:00", False),
        ]

    async def test_no_entry_carries_a_download_url(self):
        use_case = build_use_case(
            make_storage(),
            FakeStorage(["backups/db/2026-07-13T02-00-00.sql.gz.enc"], ["backups/files/x/a.png"]),
        )

        result = await use_case.execute(make_user(permissions=[Permission.WRITE_SETTINGS]))

        for entry in [*result.db, *result.files]:
            assert "url" not in entry.model_dump()


class TestWarnings:
    async def test_disabled_local_unencrypted_backups_earn_every_warning(self):
        use_case = build_use_case(
            make_storage(backup_enabled=False), FakeStorage([], []), key=False
        )

        result = await use_case.execute(make_user(permissions=[Permission.WRITE_SETTINGS]))

        assert result.warnings == [
            BackupWarning.DISABLED,
            BackupWarning.STORED_ON_HOST,
            BackupWarning.ENCRYPTION_KEY_MISSING,
        ]

    async def test_off_host_encrypted_backups_earn_none(self):
        use_case = build_use_case(make_storage(provider="s3"), FakeStorage([], []))

        result = await use_case.execute(make_user(permissions=[Permission.WRITE_SETTINGS]))

        assert result.warnings == []
