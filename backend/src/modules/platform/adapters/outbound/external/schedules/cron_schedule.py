"""
APScheduler-backed ICronSchedule: the only place that hands a cron
string to apscheduler.triggers.cron.CronTrigger, used purely to compute
"what was the latest due time", not to own a scheduled job. See
cron_schedule_port.py for how the latest-due time drives the coalescing
scheduler.
"""

from __future__ import annotations

from datetime import datetime
from datetime import timedelta

from apscheduler.triggers.cron import CronTrigger

from src.modules.platform.infrastructure.logging.logger import log


class APSchedulerCronSchedule:
    def latest_due(self, cron: str, now: datetime, grace: timedelta) -> datetime | None:
        try:
            trigger = CronTrigger.from_crontab(cron, timezone="UTC")
        except (ValueError, KeyError):
            log.error("APSchedulerCronSchedule: invalid cron %r", cron)
            return None

        window_start = now - grace
        latest: datetime | None = None
        previous: datetime | None = None
        bound = window_start
        while True:
            # CronTrigger.get_next_fire_time(previous, bound) only uses
            # `bound` to seed `start_date` when `previous` is None (see its
            # source); every later call passes the fixed `now` instead so a
            # trigger with jitter/an end_date can never wander past it. This
            # loop can run at most `grace / cron_period` times, bounded in
            # practice (grace=1h, minimum cron granularity=1min -> <=60
            # iterations), so no separate iteration cap is needed.
            candidate = trigger.get_next_fire_time(previous, bound)
            if candidate is None or candidate > now:
                break
            latest = candidate
            previous = candidate
            bound = now
        return latest
