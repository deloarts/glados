"""
create_storage_adapter maps every S3-speaking provider onto the boto3 adapter
and rejects an S3 configuration that lacks a bucket or credentials.
"""

import pytest

from src.modules.platform.adapters.outbound.external.storage.factory import create_storage_adapter
from src.modules.platform.adapters.outbound.external.storage.s3_storage import S3StorageAdapter
from src.modules.platform.domain.entities.admin_settings.storage import AdminStorageSettings
from src.modules.platform.domain.exceptions import StorageMigrationError


def _settings(provider: str, **overrides: object) -> AdminStorageSettings:
    values: dict[str, object] = dict(
        id=1,
        provider=provider,
        enabled=True,
        endpoint_url="http://seaweedfs:8333",
        public_endpoint_url=None,
        bucket_name="objects",
        access_key="key",
        secret_key="secret",
        region=None,
        use_ssl=False,
        backup_enabled=False,
        backup_path=None,
        backup_cron=None,
        backup_retention_count=7,
    )
    values.update(overrides)
    return AdminStorageSettings(**values)  # type: ignore[arg-type]


@pytest.mark.parametrize("provider", ["seaweedfs", "s3"])
def test_s3_compatible_providers_build_the_s3_adapter(provider: str) -> None:
    assert isinstance(create_storage_adapter(_settings(provider)), S3StorageAdapter)


def test_seaweedfs_without_credentials_is_rejected() -> None:
    with pytest.raises(StorageMigrationError, match="'seaweedfs'"):
        create_storage_adapter(_settings("seaweedfs", access_key=None))
