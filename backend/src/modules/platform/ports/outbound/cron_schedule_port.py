"""
Wraps APScheduler's CronTrigger as a pure cron-parsing port, so RunDueBackup
in application can compute due times without an adapter. APScheduler only
parses the expression; a 60 second tick and the backup_runs slot claim decide
when a job runs.
"""

from datetime import datetime
from datetime import timedelta
from typing import Protocol
from typing import runtime_checkable


@runtime_checkable
class ICronSchedule(Protocol):
    def latest_due(self, cron: str, now: datetime, grace: timedelta) -> datetime | None:
        """The latest fire time at or before `now`, provided it lies within
        `grace` of now; an older one counts as missed, not caught up. None
        when the expression is invalid or nothing was due in the window."""
        ...
