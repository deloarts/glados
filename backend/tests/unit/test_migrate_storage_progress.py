"""
MigrateStorage reports each object to its progress callback before copying
it, which is what lets the migration dialog name the file being copied.
"""

from src.modules.platform.application.dto.admin_settings_dto.storage import StorageMigrationProgress
from src.modules.platform.application.dto.admin_settings_dto.storage import (
    UpdateStorageSettingsCommand,
)
from src.modules.platform.application.use_cases.admin_settings.migrate_storage import MigrateStorage
from src.modules.platform.domain.value_objects.permission import Permission
from tests.unit.test_download_backup_use_case import make_actor
from tests.unit.test_storage_copy_transactions import _Events
from tests.unit.test_storage_copy_transactions import _Repo
from tests.unit.test_storage_copy_transactions import _Storage
from tests.unit.test_storage_copy_transactions import _Uow


async def test_migrate_storage_reports_each_object_before_copying_it() -> None:
    events = _Events()
    storage = _Storage(events, ["a.png", "docs/b.pdf"])

    def on_progress(event: StorageMigrationProgress) -> None:
        events.log.append(f"progress:{event.current}/{event.total}:{event.key}")

    result = await MigrateStorage(_Repo(), lambda settings: storage, uow=_Uow(events)).execute(
        actor=make_actor([Permission.WRITE_SETTINGS]),
        cmd=UpdateStorageSettingsCommand(provider="local", enabled=True),
        progress=on_progress,
    )

    assert result.committed is True
    copy_log = [entry for entry in events.log if entry != "commit"]
    assert copy_log == [
        "progress:1/2:a.png",
        "download:a.png",
        "upload:a.png",
        "progress:2/2:docs/b.pdf",
        "download:docs/b.pdf",
        "upload:docs/b.pdf",
    ]


async def test_migrate_storage_runs_without_a_progress_callback() -> None:
    events = _Events()
    storage = _Storage(events, ["a.png"])

    result = await MigrateStorage(_Repo(), lambda settings: storage, uow=_Uow(events)).execute(
        actor=make_actor([Permission.WRITE_SETTINGS]),
        cmd=UpdateStorageSettingsCommand(provider="local", enabled=True),
    )

    assert result.migrated_count == 1
