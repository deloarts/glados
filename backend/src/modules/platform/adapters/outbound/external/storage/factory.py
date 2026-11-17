"""
Build the correct IStoragePort implementation from AdminStorageSettings.
Raises StorageMigrationError when required fields are missing.
"""

from __future__ import annotations

from src.modules.platform.adapters.outbound.external.storage.azure_storage import (
    AzureStorageAdapter,
)
from src.modules.platform.adapters.outbound.external.storage.local_storage import (
    LocalStorageAdapter,
)
from src.modules.platform.adapters.outbound.external.storage.s3_storage import S3StorageAdapter
from src.modules.platform.domain.entities.admin_settings.storage import AdminStorageSettings
from src.modules.platform.domain.exceptions import StorageMigrationError
from src.modules.platform.infrastructure.config.settings import cfg
from src.modules.platform.ports.outbound.storage_port import IStoragePort


def create_storage_adapter(settings: AdminStorageSettings) -> IStoragePort:
    """Return the storage adapter for the given settings."""
    match settings.provider:
        case "local":
            return LocalStorageAdapter(base_dir=cfg.local_storage.base_dir)

        case "seaweedfs" | "s3":
            if not settings.bucket_name:
                raise StorageMigrationError(
                    f"bucket_name is required for {settings.provider!r} provider."
                )
            if not settings.access_key or not settings.secret_key:
                raise StorageMigrationError(
                    f"access_key and secret_key are required for {settings.provider!r} provider."
                )
            return S3StorageAdapter(
                bucket=settings.bucket_name,
                access_key=settings.access_key,
                secret_key=settings.secret_key,
                region=settings.region,
                endpoint_url=settings.endpoint_url,
                public_endpoint_url=settings.public_endpoint_url,
                use_ssl=settings.use_ssl,
            )

        case "azure":
            if not settings.bucket_name:
                raise StorageMigrationError(
                    "bucket_name (container name) is required for azure provider."
                )
            if not settings.access_key or not settings.secret_key:
                raise StorageMigrationError(
                    "access_key (account name) and secret_key (account key) are required for "
                    "azure provider."
                )
            return AzureStorageAdapter(
                container=settings.bucket_name,
                account_name=settings.access_key,
                account_key=settings.secret_key,
                endpoint_url=settings.endpoint_url,
            )

        case _:
            raise StorageMigrationError(f"Unknown storage provider: {settings.provider!r}.")
