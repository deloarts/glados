"""The warnings the backup configuration earns (domain/services/backup_rules.py)."""

import pytest

from src.modules.platform.domain.entities.admin_settings.storage import AdminStorageSettings
from src.modules.platform.domain.services.backup_rules import backup_warnings
from src.modules.platform.domain.value_objects.backup_warning import BackupWarning


def _warnings(key: bool = True, **overrides) -> list[BackupWarning]:
    values: dict = dict(
        id=1,
        provider="s3",
        enabled=True,
        endpoint_url=None,
        public_endpoint_url=None,
        bucket_name="b",
        access_key="a",
        secret_key="s",
        region=None,
        use_ssl=True,
        backup_enabled=True,
        backup_path="backups",
        backup_cron="0 2 * * *",
        backup_retention_count=7,
    )
    values.update(overrides)
    return backup_warnings(AdminStorageSettings(**values), encryption_key_configured=key)


def test_enabled_encrypted_off_host_backups_earn_none():
    assert _warnings(provider="s3", endpoint_url=None) == []


def test_every_warning_at_once_in_a_fixed_order():
    assert _warnings(key=False, provider="local", backup_enabled=False) == [
        BackupWarning.DISABLED,
        BackupWarning.STORED_ON_HOST,
        BackupWarning.ENCRYPTION_KEY_MISSING,
    ]


def test_no_backup_path_counts_as_disabled():
    assert _warnings(provider="s3", backup_path=None) == [BackupWarning.DISABLED]


@pytest.mark.parametrize(
    ("provider", "endpoint", "on_host"),
    [
        ("local", None, True),
        ("seaweedfs", "http://seaweedfs:8333", True),
        ("seaweedfs", "http://127.0.0.1:8333", True),
        ("seaweedfs", "https://backup.example.com", False),
        ("s3", "http://localhost:9000", False),
        ("azure", None, False),
    ],
)
def test_stored_on_host(provider, endpoint, on_host):
    warnings = _warnings(provider=provider, endpoint_url=endpoint)

    assert (BackupWarning.STORED_ON_HOST in warnings) is on_host
