"""
Domain entity for the file storage and backup settings singleton.
"""

from dataclasses import dataclass

from src.shared_kernel.domain.entities.base import Entity


@dataclass
class AdminStorageSettings(Entity):
    """File storage and backup configuration."""

    provider: str  # "local" | "seaweedfs" | "s3" | "azure"
    enabled: bool
    endpoint_url: str | None
    public_endpoint_url: str | None
    bucket_name: str | None
    access_key: str | None
    # Never returned in API responses.
    secret_key: str | None
    region: str | None
    use_ssl: bool
    backup_enabled: bool
    backup_path: str | None
    backup_cron: str | None  # cron expression, e.g. "0 2 * * *"
    backup_retention_count: int  # how many backup archives to keep
    # CheckDiskSpace warns (mail.alert_recipients) once "/" or backup_path
    # reaches this percent full. 0 = disabled.
    # Carries a dataclass default (same reasoning as
    # AdminProductionSettings.require_source_item_approval's own default)
    # so the half-dozen existing test doubles that build AdminStorageSettings
    # by hand don't all need to learn about a field they have no opinion on.
    disk_warning_percent: int = 90
