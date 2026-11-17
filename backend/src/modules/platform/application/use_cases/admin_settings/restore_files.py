"""
Copy all objects from a file snapshot prefix back to their original keys,
effectively overwriting the current active files with the snapshot contents.
Requires write:settings.
"""

from __future__ import annotations

from src.modules.platform.application.dto.admin_settings_dto.storage import RestoreFilesResult
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.exceptions import InsufficientPermissionsError
from src.modules.platform.domain.exceptions import StoragePathError
from src.modules.platform.domain.value_objects.permission import Permission
from src.modules.platform.ports.outbound.platform_settings_repository import (
    IPlatformSettingsRepository,
)
from src.modules.platform.ports.outbound.storage_port import IStorageAdapterFactory
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork


class RestoreFiles:
    def __init__(
        self,
        repo: IPlatformSettingsRepository,
        storage_factory: IStorageAdapterFactory,
        uow: IUnitOfWork | None = None,
    ) -> None:
        self._repo = repo
        self._storage_factory = storage_factory
        self._uow = uow

    async def execute(self, actor: User, snapshot_key: str) -> RestoreFilesResult:
        if not actor.has_permission(Permission.WRITE_SETTINGS):
            raise InsufficientPermissionsError("write:settings required.")

        settings = await self._repo.get_storage()

        # snapshot_key arrives straight from the request body, and it is used
        # as a storage prefix for both reads and writes. Constrain it to the
        # configured snapshot area before it reaches the adapter.
        #
        # LocalStorageAdapter._resolve() also blocks filesystem escapes, but
        # only for the local provider, S3/Azure keys are opaque, so without
        # this check an arbitrary prefix there would still copy the wrong
        # objects to the wrong places inside the bucket.
        if not settings.backup_path:
            raise StoragePathError("No backup path is configured; nothing can be restored.")

        snapshots_root = f"{settings.backup_path.rstrip('/')}/files/"
        prefix = snapshot_key.rstrip("/") + "/"

        if ".." in prefix.split("/"):
            raise StoragePathError(f"Snapshot key {snapshot_key!r} may not contain '..'.")
        if not prefix.startswith(snapshots_root):
            raise StoragePathError(
                f"Snapshot key {snapshot_key!r} is not inside the snapshot area {snapshots_root!r}."
            )
        if prefix == snapshots_root:
            # Would merge every snapshot over the live files at once.
            raise StoragePathError(
                f"Snapshot key {snapshot_key!r} must name a single snapshot, "
                "not the whole snapshot area."
            )

        # The copy loop can run for minutes and touches only storage. Ending
        # the read transaction first keeps the connection out of an idle
        # transaction the server would terminate.
        if self._uow is not None:
            await self._uow.commit()
        storage = self._storage_factory(settings)
        keys = await storage.list_keys(prefix)

        restored = 0
        for key in keys:
            original_key = key[len(prefix) :]
            if not original_key:
                continue
            data, content_type = await storage.download(key)
            await storage.upload(original_key, data, content_type)
            restored += 1

        return RestoreFilesResult(restored_count=restored)
