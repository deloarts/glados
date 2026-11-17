"""
Unit tests for APSchedulerCronSchedule.latest_due: the real "what was the
latest cron-due time within the grace window" arithmetic, isolated from
RunDueBackup's orchestration (see test_run_due_backup.py, which uses a fake
cron_schedule and never exercises this class).
"""

import logging
from datetime import UTC
from datetime import datetime
from datetime import timedelta

from src.modules.platform.adapters.outbound.external.schedules.cron_schedule import (
    APSchedulerCronSchedule,
)

GRACE = timedelta(hours=1)


def make() -> APSchedulerCronSchedule:
    return APSchedulerCronSchedule()


class TestNothingDue:
    def test_a_future_only_cron_within_the_window_returns_none(self):
        # "* * * * *" every minute IS always due, so use a cron that only
        # fires at a fixed time of day far from `now` in both directions.
        now = datetime(2026, 8, 28, 10, 0, 0, tzinfo=UTC)
        due = make().latest_due("0 2 * * *", now, GRACE)  # daily at 02:00, now is 10:00
        assert due is None


class TestWithinGrace:
    def test_a_fire_time_a_few_minutes_ago_is_returned(self):
        now = datetime(2026, 8, 28, 10, 13, 27, tzinfo=UTC)
        due = make().latest_due("*/5 * * * *", now, GRACE)  # every 5 minutes
        assert due == datetime(2026, 8, 28, 10, 10, 0, tzinfo=UTC)

    def test_returns_the_latest_due_time_not_the_earliest(self):
        """Several 5-minute fire times fall inside the 1h grace window; the
        latest one (closest to now) is the one that should run, not the
        oldest one that was ever missed."""
        now = datetime(2026, 8, 28, 10, 13, 0, tzinfo=UTC)
        due = make().latest_due("*/5 * * * *", now, GRACE)
        assert due == datetime(2026, 8, 28, 10, 10, 0, tzinfo=UTC)

    def test_fire_time_exactly_at_now_is_returned(self):
        now = datetime(2026, 8, 28, 10, 15, 0, tzinfo=UTC)
        due = make().latest_due("*/5 * * * *", now, GRACE)
        assert due == now


class TestOutsideGrace:
    def test_a_fire_time_older_than_the_grace_window_is_not_caught_up(self):
        # Daily cron, last fired ~8h before `now`, grace is only 1h.
        now = datetime(2026, 8, 28, 10, 0, 0, tzinfo=UTC)
        due = make().latest_due("0 2 * * *", now, GRACE)
        assert due is None

    def test_a_fire_time_just_inside_the_grace_window_is_still_returned(self):
        now = datetime(2026, 8, 28, 3, 0, 0, tzinfo=UTC)  # 1h after 02:00
        due = make().latest_due("0 2 * * *", now, GRACE)
        assert due == datetime(2026, 8, 28, 2, 0, 0, tzinfo=UTC)


class TestInvalidCron:
    def test_an_invalid_expression_returns_none_and_logs_an_error(self, glados_caplog):
        now = datetime(2026, 8, 28, 10, 0, 0, tzinfo=UTC)
        due = make().latest_due("not a cron expression", now, GRACE)
        assert due is None
        assert [r for r in glados_caplog.records if r.levelno == logging.ERROR]
