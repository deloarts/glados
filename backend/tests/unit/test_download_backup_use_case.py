"""
Unit tests for DownloadBackup, the Item-3 Family-3 admin route that streams
a single DB archive or file-snapshot object's raw bytes. Gated on
write:settings (a full DB dump exposes every password hash and TOTP
secret), and constrained to the configured backup_path prefix as defence
in depth on top of
LocalStorageAdapter._resolve() (the only containment S3/Azure get, since
their keys are opaque strings).
"""

from datetime import UTC
from datetime import datetime

import pytest

from src.modules.platform.application.use_cases.admin_settings.download_backup import DownloadBackup
from src.modules.platform.domain.entities.admin_settings.storage import AdminStorageSettings
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.exceptions import BackupNotConfiguredError
from src.modules.platform.domain.exceptions import InsufficientPermissionsError
from src.modules.platform.domain.exceptions import StoragePathError
from src.modules.platform.domain.value_objects.date_format import DateFormat
from src.modules.platform.domain.value_objects.language import Language
from src.modules.platform.domain.value_objects.permission import Permission
from src.modules.platform.domain.value_objects.start_page import StartPage
from src.modules.platform.domain.value_objects.theme import ThemePreset
from src.modules.platform.domain.value_objects.theme import ThemePrimary
from src.modules.platform.domain.value_objects.theme import ThemeSurface
from src.modules.platform.ports.outbound.storage_port import StoredObjectStream


def make_actor(permissions: list[str] | None = None) -> User:
    return User(
        id=1,
        username="tester",
        full_name="Test User",
        email="tester@example.com",
        created=datetime.now(UTC),
        hashed_password="x",
        is_active=True,
        is_systemuser=False,
        permissions=permissions if permissions is not None else [],
        language=Language.enGB,
        date_format=DateFormat.ISO,
        start_page=StartPage.DASHBOARD,
        theme_preset=ThemePreset.Aura,
        theme_surface=ThemeSurface.glados,
        theme_primary=ThemePrimary.glados,
        theme_dark_mode=False,
        button_flat_style=False,
        table_gridlines=False,
        table_striped_rows=False,
    )


def _storage_settings(
    *, backup_enabled: bool = True, backup_path: str | None = "backups"
) -> AdminStorageSettings:
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
        use_ssl=True,
        backup_enabled=backup_enabled,
        backup_path=backup_path,
        backup_cron=None,
        backup_retention_count=7,
    )


class FakeAdminSettingsRepo:
    def __init__(self, settings: AdminStorageSettings) -> None:
        self._settings = settings

    async def get_storage(self) -> AdminStorageSettings:
        return self._settings


class FakeStorage:
    def __init__(self, objects: dict[str, tuple[bytes, str]]) -> None:
        self._objects = objects

    async def download(self, key: str) -> tuple[bytes, str]:
        return self._objects[key]

    async def open_stream(self, key: str) -> StoredObjectStream:
        data, content_type = self._objects[key]

        async def chunks():
            yield data

        return StoredObjectStream(content_type=content_type, size=len(data), chunks=chunks())


def fake_storage_factory(objects: dict[str, tuple[bytes, str]]):
    def factory(settings: AdminStorageSettings) -> FakeStorage:
        return FakeStorage(objects)

    return factory


async def test_unprivileged_cannot_download_a_backup() -> None:
    repo = FakeAdminSettingsRepo(_storage_settings())
    uc = DownloadBackup(repo, fake_storage_factory({}))

    with pytest.raises(InsufficientPermissionsError):
        await uc.execute(actor=make_actor([]), key="backups/db/2026-01-01T00-00-00.sql.gz")


async def test_admin_downloads_a_db_archive() -> None:
    repo = FakeAdminSettingsRepo(_storage_settings())
    key = "backups/db/2026-01-01T00-00-00.sql.gz"
    uc = DownloadBackup(repo, fake_storage_factory({key: (b"gzip-bytes", "application/gzip")}))

    stream = await uc.execute(actor=make_actor([Permission.WRITE_SETTINGS]), key=key)

    assert b"".join([chunk async for chunk in stream.chunks]) == b"gzip-bytes"
    assert stream.content_type == "application/gzip"


@pytest.mark.parametrize("key", ["users/avatars/1.jpg", "../.env"])
async def test_key_outside_the_backup_prefix_is_rejected(key: str) -> None:
    repo = FakeAdminSettingsRepo(_storage_settings())
    uc = DownloadBackup(repo, fake_storage_factory({}))

    with pytest.raises(StoragePathError):
        await uc.execute(actor=make_actor([Permission.WRITE_SETTINGS]), key=key)


async def test_download_when_backups_are_disabled_raises() -> None:
    repo = FakeAdminSettingsRepo(_storage_settings(backup_enabled=False))
    uc = DownloadBackup(repo, fake_storage_factory({}))

    with pytest.raises(BackupNotConfiguredError):
        await uc.execute(
            actor=make_actor([Permission.WRITE_SETTINGS]),
            key="backups/db/2026-01-01T00-00-00.sql.gz",
        )
