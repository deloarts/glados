"""
Status and trigger enums for BackupRun, mirroring PrintJobStatus /
PrintJobTrigger's str-Enum style (print_classifier.py): the entity itself
keeps a plain `status: str` / `trigger: str` field (see print_job.py's
precedent), the application layer constructs/compares with these, and the
repository stores/reads the plain values.
"""

from enum import Enum
from enum import unique


@unique
class BackupRunStatus(str, Enum):
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"


@unique
class BackupRunTrigger(str, Enum):
    SCHEDULED = "scheduled"
    MANUAL = "manual"
