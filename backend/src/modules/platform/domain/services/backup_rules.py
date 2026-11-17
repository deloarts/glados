"""
Which warnings the backup configuration earns. Shared by the Backups tab
and the readiness probe, so both report the same conditions.
"""

from urllib.parse import urlparse

from src.modules.platform.domain.entities.admin_settings.storage import AdminStorageSettings
from src.modules.platform.domain.value_objects.backup_warning import BackupWarning

# Host names that put an object store on the database's own host: the
# object store docker-compose.yml bundles, reached by its service name, and
# the loopback address.
_ON_HOST_NAMES = frozenset({"seaweedfs", "localhost", "127.0.0.1", "::1"})


def stored_on_host(settings: AdminStorageSettings) -> bool:
    """True when the archives land on the host that runs the database."""
    if settings.provider == "local":
        return True
    if settings.provider == "seaweedfs" and settings.endpoint_url:
        host = urlparse(settings.endpoint_url).hostname
        return host is not None and host.lower() in _ON_HOST_NAMES
    return False


def backup_warnings(
    settings: AdminStorageSettings, *, encryption_key_configured: bool
) -> list[BackupWarning]:
    """The warnings for the current settings, in a fixed order. A disabled
    backup still reports where archives would go, so fixing one warning
    never reveals another the operator could have seen at once."""
    warnings: list[BackupWarning] = []
    if not settings.backup_enabled or not settings.backup_path:
        warnings.append(BackupWarning.DISABLED)
    if stored_on_host(settings):
        warnings.append(BackupWarning.STORED_ON_HOST)
    if not encryption_key_configured:
        warnings.append(BackupWarning.ENCRYPTION_KEY_MISSING)
    return warnings
