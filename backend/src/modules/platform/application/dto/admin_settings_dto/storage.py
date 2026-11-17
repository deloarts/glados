"""
Commands and results for the file storage settings, storage migration, backups
and file restore.
"""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from pydantic import BaseModel
from pydantic import Field

from src.modules.platform.application.dto.base import ResultBase
from src.modules.platform.domain.value_objects.backup_run_status import BackupRunStatus
from src.modules.platform.domain.value_objects.backup_run_status import BackupRunTrigger
from src.modules.platform.domain.value_objects.backup_warning import BackupWarning


class UpdateStorageSettingsCommand(BaseModel):
    provider: str  # "local" | "seaweedfs" | "s3" | "azure"
    enabled: bool
    endpoint_url: str | None = None
    public_endpoint_url: str | None = None
    bucket_name: str | None = None
    access_key: str | None = None
    # None means "keep existing secret unchanged"
    secret_key: str | None = None
    region: str | None = None
    use_ssl: bool = True
    backup_enabled: bool = False
    backup_path: str | None = None
    backup_cron: str | None = None
    backup_retention_count: int = 7
    # CheckDiskSpace's warning threshold, percent
    # full on "/" or backup_path. 0 = disabled.
    disk_warning_percent: int = Field(default=90, ge=0, le=100)


class AdminStorageSettingsResult(ResultBase):
    provider: str
    enabled: bool
    endpoint_url: str | None
    public_endpoint_url: str | None
    bucket_name: str | None
    access_key: str | None
    secret_key_configured: bool  # True if a secret key is stored
    region: str | None
    use_ssl: bool
    backup_enabled: bool
    backup_path: str | None
    backup_cron: str | None
    backup_retention_count: int
    disk_warning_percent: int


class StorageMigrationResult(BaseModel):
    migrated_count: int
    failed_count: int
    errors: list[str]
    committed: bool  # True if new settings were saved to DB


@dataclass
class StorageMigrationProgress:
    """Sent before each object is copied: `current` is its 1-based position
    among the `total` objects found on the source provider."""

    current: int
    total: int
    key: str


StorageMigrationProgressCallback = Callable[[StorageMigrationProgress], None]


class BackupEntryResult(BaseModel):
    """One DB archive or file snapshot. There is deliberately no download
    URL: a presigned URL would hand the archive to whoever holds the link,
    so downloads go through the authenticated download route only."""

    key: str
    timestamp: str
    # True for an archive written with the backup encryption key; always
    # False for a file snapshot.
    encrypted: bool


class BackupRunEntryResult(BaseModel):
    """One backup_runs row, as ListBackups exposes it."""

    slot: datetime
    trigger: BackupRunTrigger
    status: BackupRunStatus
    started_at: datetime
    finished_at: datetime | None
    error: str | None


class BackupListResult(BaseModel):
    db: list[BackupEntryResult]
    files: list[BackupEntryResult]
    warnings: list[BackupWarning]  # see domain/services/backup_rules.py
    last_run: BackupRunEntryResult | None  # runs[0], the most recent attempt of either kind
    runs: list[BackupRunEntryResult]  # newest first, last 20


class RestoreFilesCommand(BaseModel):
    snapshot_key: str  # prefix of the file snapshot, e.g. "backups/files/2026-07-13T02-00-00"


class RestoreFilesResult(BaseModel):
    restored_count: int
