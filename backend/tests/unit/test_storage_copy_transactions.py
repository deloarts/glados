"""
Storage migration and file-snapshot restore copy objects for as long as the
store takes, so both end their read transaction before the copy loop
starts instead of leaving the connection idle in a transaction.
"""

from src.modules.platform.application.dto.admin_settings_dto.storage import (
    UpdateStorageSettingsCommand,
)
from src.modules.platform.application.use_cases.admin_settings.migrate_storage import MigrateStorage
from src.modules.platform.application.use_cases.admin_settings.restore_files import RestoreFiles
from src.modules.platform.domain.value_objects.permission import Permission
from tests.unit.test_download_backup_use_case import _storage_settings
from tests.unit.test_download_backup_use_case import make_actor


class _Events:
    def __init__(self) -> None:
        self.log: list[str] = []


class _Uow:
    def __init__(self, events: _Events) -> None:
        self._events = events

    async def commit(self) -> None:
        self._events.log.append("commit")

    async def rollback(self) -> None:
        self._events.log.append("rollback")


class _Storage:
    def __init__(self, events: _Events, keys: list[str]) -> None:
        self._events = events
        self._keys = keys

    async def list_keys(self, prefix: str = "") -> list[str]:
        return [k for k in self._keys if k.startswith(prefix)]

    async def download(self, key: str) -> tuple[bytes, str]:
        self._events.log.append(f"download:{key}")
        return b"x", "application/octet-stream"

    async def upload(self, key: str, data: bytes, content_type: str) -> None:
        self._events.log.append(f"upload:{key}")


class _Repo:
    async def get_storage(self):
        return _storage_settings()

    async def save_storage(self, settings) -> None:
        pass

    async def append_audit(self, entry) -> None:
        pass


async def test_storage_migration_ends_the_read_transaction_before_copying() -> None:
    events = _Events()
    storage = _Storage(events, ["a.png", "b.png"])

    await MigrateStorage(_Repo(), lambda settings: storage, uow=_Uow(events)).execute(
        actor=make_actor([Permission.WRITE_SETTINGS]),
        cmd=UpdateStorageSettingsCommand(provider="local", enabled=True),
    )

    assert events.log[0] == "commit"
    assert "download:a.png" in events.log


async def test_file_restore_ends_the_read_transaction_before_copying() -> None:
    events = _Events()
    storage = _Storage(events, ["backups/files/snap-1/a.png"])

    result = await RestoreFiles(_Repo(), lambda settings: storage, uow=_Uow(events)).execute(
        actor=make_actor([Permission.WRITE_SETTINGS]), snapshot_key="backups/files/snap-1"
    )

    assert events.log == ["commit", "download:backups/files/snap-1/a.png", "upload:a.png"]
    assert result.restored_count == 1
