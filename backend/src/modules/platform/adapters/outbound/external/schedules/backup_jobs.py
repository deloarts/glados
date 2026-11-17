"""
IBackupJobs adapter: thin wrapper over the existing DatabaseBackupJob /
FileBackupJob so RunClaimedBackup (application layer) can run them behind a
port. It hands the database job the backup encryption key from the
environment.
"""

from __future__ import annotations

from src.modules.platform.adapters.outbound.external.schedules.database_schedule import (
    DatabaseBackupJob,
)
from src.modules.platform.adapters.outbound.external.schedules.file_schedule import FileBackupJob
from src.modules.platform.domain.entities.admin_settings.storage import AdminStorageSettings
from src.modules.platform.infrastructure.config.settings import cfg


class ScheduledBackupJobs:
    def __init__(self, settings: AdminStorageSettings, db_url: str) -> None:
        self._settings = settings
        self._db_url = db_url

    async def run_db(self) -> str:
        # Debug mode is the only place an unencrypted archive is acceptable,
        # since a development stack has no backup key to lose.
        return await DatabaseBackupJob(
            settings=self._settings,
            db_url=self._db_url,
            encryption_key=cfg.security.backup_encryption_key,
            require_encryption=not cfg.debug,
        ).run()

    async def run_files(self) -> str:
        return await FileBackupJob(settings=self._settings).run()
