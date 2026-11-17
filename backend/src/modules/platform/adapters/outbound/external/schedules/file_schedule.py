"""
Scheduled job: snapshot all active storage files into a timestamped prefix
under backup_path, then enforce the retention limit.
"""

from __future__ import annotations

from src.modules.platform.adapters.outbound.external.storage.factory import create_storage_adapter
from src.modules.platform.domain.entities.admin_settings.storage import AdminStorageSettings
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.ports.outbound.storage_port import IStoragePort
from src.shared_kernel.domain.services.clock import now_utc


class FileBackupJob:
    def __init__(self, settings: AdminStorageSettings) -> None:
        self._settings = settings

    async def run(self) -> str:
        settings = self._settings
        if not settings.backup_path:
            from src.modules.platform.domain.exceptions import BackupError

            raise BackupError("backup_path is not configured.")
        log.info("File backup: starting snapshot")
        storage = create_storage_adapter(settings)

        backup_prefix = settings.backup_path.rstrip("/")
        timestamp = now_utc().strftime("%Y-%m-%dT%H-%M-%S")
        snapshot_prefix = f"{backup_prefix}/files/{timestamp}/"

        all_keys = await storage.list_keys()
        # Exclude anything already under the backup prefix to avoid recursive growth
        active_keys = [k for k in all_keys if not k.startswith(f"{backup_prefix}/")]

        for key in active_keys:
            data, content_type = await storage.download(key)
            await storage.upload(f"{snapshot_prefix}{key}", data, content_type)

        log.info("File backup: snapshot %r, %d files", snapshot_prefix, len(active_keys))
        await self._enforce_retention(storage, settings)
        return snapshot_prefix

    async def _enforce_retention(
        self, storage: IStoragePort, settings: AdminStorageSettings
    ) -> None:
        assert settings.backup_path
        files_prefix = f"{settings.backup_path.rstrip('/')}/files/"
        all_keys = await storage.list_keys(files_prefix)

        snapshots: set[str] = set()
        for key in all_keys:
            rel = key[len(files_prefix) :]
            segment = rel.split("/")[0]
            if segment:
                snapshots.add(segment)

        sorted_snapshots = sorted(snapshots)
        excess = len(sorted_snapshots) - settings.backup_retention_count
        pruned = sorted_snapshots[: max(0, excess)]
        for ts in pruned:
            snap_prefix = f"{files_prefix}{ts}/"
            for key in await storage.list_keys(snap_prefix):
                await storage.delete(key)
            log.debug("File backup: pruned old snapshot %r", ts)
        if pruned:
            log.info("File backup: pruned %d old snapshot(s)", len(pruned))
