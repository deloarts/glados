"""
One durable record of a backup attempt (scheduled tick or manual run-now).
The `slot` field is the exactly-once claim key across gunicorn's four worker
processes. See IBackupRunRepository.try_claim. Append-mostly: a row is
created "running" the instant its slot is claimed and updated exactly once
more, by RunClaimedBackup.finish, to its terminal status.
"""

from dataclasses import dataclass
from datetime import datetime

from src.modules.platform.domain.value_objects.backup_run_status import BackupRunStatus
from src.modules.platform.domain.value_objects.backup_run_status import BackupRunTrigger
from src.shared_kernel.domain.entities.base import Entity


@dataclass
class BackupRun(Entity):
    slot: datetime  # cron due time (scheduled) or claim instant (manual)
    trigger: BackupRunTrigger
    started_at: datetime
    finished_at: datetime | None
    status: BackupRunStatus
    db_key: str | None
    files_key: str | None
    error: str | None
    worker: str  # hostname-pid of the claiming process
