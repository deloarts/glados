"""
The reasons the backups of a deployment do not protect it fully, as the
Backups tab and the readiness probe report them.
"""

from enum import unique

from src.shared_kernel.domain.value_objects.value_enum import StrValueEnum


@unique
class BackupWarning(StrValueEnum):
    # Scheduled backups are switched off or have no backup path.
    DISABLED = "disabled"
    # The archives are stored on the host that runs the database: the local
    # provider, or an object store reached by a compose service name or the
    # loopback address. One disk or host failure then takes both.
    STORED_ON_HOST = "stored_on_host"
    # SECURITY__BACKUP_ENCRYPTION_KEY is not set, so a production process
    # refuses to write a backup at all.
    ENCRYPTION_KEY_MISSING = "encryption_key_missing"
