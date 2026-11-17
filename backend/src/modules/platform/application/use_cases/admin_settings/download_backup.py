"""
Stream a single DB archive or file-snapshot object's raw bytes back to an
admin. The object is opened for chunked reading rather than loaded whole,
since a database archive can be far larger than a worker should hold in
memory. A full DB dump contains every password hash and TOTP secret, more
than "settings read" implies, so this is gated on write:settings,
treating a download as an operator action rather than a settings read.
ListBackups is gated the same way so listing and downloading agree.
"""

from __future__ import annotations

from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.exceptions import BackupNotConfiguredError
from src.modules.platform.domain.exceptions import InsufficientPermissionsError
from src.modules.platform.domain.exceptions import StoragePathError
from src.modules.platform.domain.value_objects.permission import Permission
from src.modules.platform.ports.outbound.platform_settings_repository import (
    IPlatformSettingsRepository,
)
from src.modules.platform.ports.outbound.storage_port import IStorageAdapterFactory
from src.modules.platform.ports.outbound.storage_port import StoredObjectStream


class DownloadBackup:
    def __init__(
        self, repo: IPlatformSettingsRepository, storage_factory: IStorageAdapterFactory
    ) -> None:
        self._repo = repo
        self._storage_factory = storage_factory

    async def execute(self, actor: User, key: str) -> StoredObjectStream:
        if not actor.has_permission(Permission.WRITE_SETTINGS):
            raise InsufficientPermissionsError("write:settings required.")

        settings = await self._repo.get_storage()
        if not settings.backup_enabled or not settings.backup_path:
            raise BackupNotConfiguredError(
                "Backup is not enabled or backup_path is not configured."
            )

        backup_prefix = settings.backup_path.rstrip("/")
        allowed_prefixes = (f"{backup_prefix}/db/", f"{backup_prefix}/files/")

        # `key` arrives straight from the query string and is used as a
        # storage key. Constrain it to the configured backup area before it
        # reaches the adapter: defence in depth on top of
        # LocalStorageAdapter._resolve(), and the only containment S3/Azure
        # get (their keys are opaque strings, "../" is just part of the name
        # to them).
        if ".." in key.split("/") or not key.startswith(allowed_prefixes):
            raise StoragePathError(f"Backup key {key!r} is not inside the backup area.")

        storage = self._storage_factory(settings)
        return await storage.open_stream(key)
