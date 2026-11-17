"""
Wraps DatabaseBackupJob / FileBackupJob (adapters) behind a port so the
application-layer use cases that run an already-claimed backup_runs row
(RunClaimedBackup, driven by RunDueBackup and the run-now endpoint) depend
only on a port, per the hexagonal layering rule.
"""

from typing import Protocol
from typing import runtime_checkable

from src.modules.platform.domain.entities.admin_settings.storage import AdminStorageSettings


@runtime_checkable
class IBackupJobs(Protocol):
    async def run_db(self) -> str:
        """Runs pg_dump, uploads the compressed archive, returns its
        storage key. Raises BackupError on failure."""
        ...

    async def run_files(self) -> str:
        """Snapshots active storage into a timestamped prefix, returns the
        prefix. Raises BackupError on failure."""
        ...


@runtime_checkable
class IBackupJobsFactory(Protocol):
    def __call__(self, settings: AdminStorageSettings, db_url: str) -> IBackupJobs:
        """Build the IBackupJobs implementation for the given storage settings
        and database URL.

        A factory port rather than a single injected IBackupJobs because the
        run-now endpoint answers 202/409 synchronously and only then, in a
        background task on a fresh session, reads the settings the jobs need.
        """
        ...
