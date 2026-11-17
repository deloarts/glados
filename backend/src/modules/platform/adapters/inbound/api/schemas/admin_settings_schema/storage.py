"""
HTTP request and response schemas for the file storage settings, storage
migration, backups and file restore.
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field

from src.modules.platform.adapters.inbound.api.schemas.base import EntityResponse
from src.modules.platform.adapters.inbound.api.schemas.base import ResponseModel
from src.modules.platform.domain.value_objects.backup_run_status import BackupRunStatus
from src.modules.platform.domain.value_objects.backup_run_status import BackupRunTrigger
from src.modules.platform.domain.value_objects.backup_warning import BackupWarning


class UpdateStorageSettingsRequest(BaseModel):
    provider: str
    enabled: bool
    endpoint_url: str | None = None
    public_endpoint_url: str | None = None
    bucket_name: str | None = None
    access_key: str | None = None
    secret_key: str | None = None
    region: str | None = None
    use_ssl: bool = True
    backup_enabled: bool = False
    backup_path: str | None = None
    backup_cron: str | None = None
    backup_retention_count: int = 7
    # CheckDiskSpace's warning threshold, percent full on "/" or
    # backup_path. 0 = disabled. Mirrored on
    # UpdateStorageSettingsCommand per the package's docstring.
    disk_warning_percent: int = Field(default=90, ge=0, le=100)


class RestoreFilesRequest(BaseModel):
    snapshot_key: str


class AdminStorageSettingsResponse(EntityResponse):
    provider: Literal["local", "seaweedfs", "s3", "azure"]
    enabled: bool
    endpoint_url: str | None
    public_endpoint_url: str | None
    bucket_name: str | None
    access_key: str | None
    secret_key_configured: bool
    region: str | None
    use_ssl: bool
    backup_enabled: bool
    backup_path: str | None
    backup_cron: str | None
    backup_retention_count: int
    disk_warning_percent: int


class StorageMigrationResponse(ResponseModel):
    migrated_count: int
    failed_count: int
    errors: list[str]
    committed: bool


class StorageMigrationRunResponse(ResponseModel):
    """The running migration, built from the run registry's RunState.
    `current`/`total`/`detail` are the progress the runner's own stream
    carries, refreshed every heartbeat; `detail` is the key being copied."""

    user_name: str
    started_at: str
    current: int | None
    total: int | None
    detail: str | None

    model_config = ConfigDict(from_attributes=True)


class StorageMigrationStatusResponse(ResponseModel):
    """GET /storage/migrate/status, how a reloaded page or a client that lost
    its stream finds a migration that is still running."""

    running: bool
    run: StorageMigrationRunResponse | None


class BackupEntryResponse(ResponseModel):
    key: str
    timestamp: str
    encrypted: bool


class BackupRunEntryResponse(ResponseModel):
    slot: datetime
    trigger: BackupRunTrigger
    status: BackupRunStatus
    started_at: datetime
    finished_at: datetime | None
    error: str | None


class BackupListResponse(ResponseModel):
    db: list[BackupEntryResponse]
    files: list[BackupEntryResponse]
    warnings: list[BackupWarning]
    last_run: BackupRunEntryResponse | None
    runs: list[BackupRunEntryResponse]


class RestoreFilesResponse(ResponseModel):
    restored_count: int
