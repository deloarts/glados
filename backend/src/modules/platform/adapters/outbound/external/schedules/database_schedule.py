"""
Scheduled job: pg_dump the configured database, gzip and encrypt it, upload
it to storage, and enforce the retention limit by deleting the oldest
archives.

Outside debug mode the job refuses to run without a backup encryption key,
so no unencrypted archive ever reaches the backup storage, which may well
be off the host. The refusal fails the run, which the run history, the
schedule-error mail and the backup failure metric all report.
"""

from __future__ import annotations

from functools import partial

from anyio import to_thread

from src.modules.platform.adapters.outbound.external.schedules.database_dump import build_archive
from src.modules.platform.adapters.outbound.external.schedules.database_dump import dump_database
from src.modules.platform.adapters.outbound.external.storage.factory import create_storage_adapter
from src.modules.platform.domain.entities.admin_settings.storage import AdminStorageSettings
from src.modules.platform.domain.exceptions import BackupError
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.ports.outbound.storage_port import IStoragePort
from src.shared_kernel.domain.services.clock import now_utc

MISSING_KEY_MESSAGE = (
    "SECURITY__BACKUP_ENCRYPTION_KEY is not set, and Glados writes no unencrypted "
    "backup outside debug mode. Set the key in the env file and restart the backend."
)


class DatabaseBackupJob:
    def __init__(
        self,
        settings: AdminStorageSettings,
        db_url: str,
        *,
        encryption_key: str | None = None,
        require_encryption: bool = True,
    ) -> None:
        self._settings = settings
        self._db_url = db_url
        self._encryption_key = encryption_key or None
        self._require_encryption = require_encryption

    async def run(self) -> str:
        settings = self._settings
        if not settings.backup_path:
            raise BackupError("backup_path is not configured.")
        if self._encryption_key is None:
            if self._require_encryption:
                raise BackupError(MISSING_KEY_MESSAGE)
            log.warning(
                "DB backup: SECURITY__BACKUP_ENCRYPTION_KEY is not set, writing an "
                "unencrypted archive (debug mode only)."
            )
        log.info("DB backup: starting pg_dump")
        storage = create_storage_adapter(settings)

        dump = await dump_database(self._db_url)
        archive = await to_thread.run_sync(partial(build_archive, dump, self._encryption_key))
        timestamp = now_utc().strftime("%Y-%m-%dT%H-%M-%S")
        key = f"{settings.backup_path.rstrip('/')}/db/{timestamp}{archive.suffix}"
        await storage.upload(key, archive.data, archive.content_type)
        log.info(
            "DB backup: uploaded %r (%d bytes, %s)",
            key,
            len(archive.data),
            "encrypted" if archive.encrypted else "unencrypted",
        )

        await self._enforce_retention(storage, settings)
        return key

    async def _enforce_retention(
        self, storage: IStoragePort, settings: AdminStorageSettings
    ) -> None:
        assert settings.backup_path
        prefix = f"{settings.backup_path.rstrip('/')}/db/"
        # The timestamp leads every file name, so plain and encrypted
        # archives sort together by age.
        keys = sorted(await storage.list_keys(prefix))
        excess = len(keys) - settings.backup_retention_count
        pruned = keys[: max(0, excess)]
        for key in pruned:
            await storage.delete(key)
            log.debug("DB backup: pruned old archive %r", key)
        if pruned:
            log.info("DB backup: pruned %d old archive(s)", len(pruned))
