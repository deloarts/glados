"""
A machine calendar's hours are local to the tenant's zone: each interval
starts at a local time, is converted with its own day's offset across a
daylight saving change, and belongs to the day it starts on, a night shift
past midnight included. Tenant holidays close a day under the machine's
own exceptions, and a downtime is cut out of the windows where it falls.
"""

from datetime import UTC
from datetime import date
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from src.modules.fulfillment.domain.entities.machine_downtime import MachineDowntime
from src.modules.fulfillment.domain.services.scheduling import WorkInterval
from src.modules.fulfillment.domain.services.scheduling import apply_downtimes
from src.modules.fulfillment.domain.services.scheduling import build_machine_calendar
from src.modules.fulfillment.domain.services.scheduling import compute_daily_capacity
from src.modules.fulfillment.domain.services.scheduling import place
from src.modules.fulfillment.domain.services.scheduling import validate_day_hours
from src.modules.fulfillment.domain.services.scheduling import validate_weekly_hours
from src.modules.fulfillment.domain.value_objects.machine_downtime_reason import (
    MachineDowntimeReason,
)
from src.modules.platform.domain.exceptions import InvalidScheduleCalendarError

VIENNA = ZoneInfo("Europe/Vienna")
# Europe/Vienna switches to summer time on Sunday 2026-03-29 and back on
# Sunday 2026-10-25.
FRIDAY_BEFORE_SPRING = date(2026, 3, 27)
MONDAY_AFTER_SPRING = date(2026, 3, 30)
MONDAY = date(2026, 7, 27)
TUESDAY = date(2026, 7, 28)


def _week(hours) -> dict:
    return {weekday: hours if weekday < 5 else 0 for weekday in range(7)}


def _utc(*args: int) -> datetime:
    return datetime(*args, tzinfo=UTC)


def test_a_day_starts_at_its_local_time_on_both_sides_of_a_dst_change():
    calendar = build_machine_calendar(_week(480), None, {}, zone=VIENNA)

    # 08:00 is 07:00 UTC in winter time and 06:00 UTC in summer time.
    assert calendar.windows_on(FRIDAY_BEFORE_SPRING) == (
        (_utc(2026, 3, 27, 7), _utc(2026, 3, 27, 15)),
    )
    assert calendar.windows_on(MONDAY_AFTER_SPRING) == (
        (_utc(2026, 3, 30, 6), _utc(2026, 3, 30, 14)),
    )


def test_a_night_shift_past_midnight_belongs_to_the_day_it_starts():
    night = [WorkInterval(start_minute=22 * 60, minutes=480)]
    calendar = build_machine_calendar(_week(night), None, {}, zone=VIENNA)

    # Monday 22:00 to Tuesday 06:00 local, summer time.
    assert calendar.windows_on(MONDAY) == ((_utc(2026, 7, 27, 20), _utc(2026, 7, 28, 4)),)
    assert calendar.minutes_available_on(MONDAY) == 480

    # An order of ten hours starting Monday 23:00 local fills the rest of
    # Monday's shift and continues in Tuesday's.
    start, end = place(_utc(2026, 7, 27, 21), 600, calendar)

    assert start == _utc(2026, 7, 27, 21)
    assert end == _utc(2026, 7, 28, 23)


def test_a_split_day_places_work_in_both_of_its_intervals():
    split = [WorkInterval(6 * 60, 240), WorkInterval(14 * 60, 240)]
    calendar = build_machine_calendar(_week(split), None, {}, zone=UTC)

    start, end = place(_utc(2026, 7, 27, 0), 300, calendar)

    assert (start, end) == (_utc(2026, 7, 27, 6), _utc(2026, 7, 27, 15))
    assert calendar.minutes_available_on(MONDAY) == 480


def test_windows_of_consecutive_days_that_touch_are_merged():
    """Monday's night shift ends when Tuesday's early shift starts, so a
    placement runs on without a gap."""
    hours = [WorkInterval(0, 360), WorkInterval(22 * 60, 120)]
    calendar = build_machine_calendar(_week(hours), None, {}, zone=UTC)

    start, end = place(_utc(2026, 7, 27, 22), 240, calendar)

    assert (start, end) == (_utc(2026, 7, 27, 22), _utc(2026, 7, 28, 2))


def test_a_holiday_closes_the_day_and_a_machine_exception_reopens_it():
    holiday = MONDAY
    closed = build_machine_calendar(_week(480), None, {}, holidays=[holiday])
    reopened = build_machine_calendar(_week(480), None, {holiday: 240}, holidays=[holiday])

    assert closed.minutes_available_on(holiday) == 0
    assert closed.minutes_available_on(TUESDAY) == 480
    assert reopened.minutes_available_on(holiday) == 240


def test_a_downtime_in_the_middle_of_a_shift_keeps_the_work_out_of_it():
    calendar = build_machine_calendar(_week(480), None, {})
    downtime = MachineDowntime(
        id=1,
        created=_utc(2026, 7, 20),
        changed=None,
        changes=[],
        machine_id=1,
        started_at=_utc(2026, 7, 27, 10),
        ended_at=_utc(2026, 7, 27, 11),
        reason=MachineDowntimeReason.MAINTENANCE,
        note=None,
        reported_by_id=1,
        ended_by_id=None,
    )
    blocked = apply_downtimes(calendar, [downtime], _utc(2026, 7, 27, 7))

    start, end = place(_utc(2026, 7, 27, 8), 180, blocked)

    # Two hours before the downtime, then one after it.
    assert (start, end) == (_utc(2026, 7, 27, 8), _utc(2026, 7, 27, 12))
    assert blocked.minutes_available_on(MONDAY) == 420


def test_capacity_counts_a_night_shift_on_its_starting_day():
    night = [WorkInterval(start_minute=22 * 60, minutes=480)]
    calendar = build_machine_calendar(_week(night), None, {}, zone=UTC)

    capacity = compute_daily_capacity(calendar, [], [MONDAY, TUESDAY])

    assert capacity == {MONDAY: (0, 480), TUESDAY: (0, 480)}


@pytest.mark.parametrize(
    "hours",
    [
        1441,
        -1,
        [WorkInterval(1440, 60)],
        [WorkInterval(-1, 60)],
        [WorkInterval(8 * 60, 1441)],
        [WorkInterval(8 * 60, 480), WorkInterval(15 * 60, 60)],
        [WorkInterval(0, 1000), WorkInterval(1000, 500)],
    ],
)
def test_a_day_beyond_its_bounds_or_with_overlapping_intervals_is_refused(hours):
    with pytest.raises(InvalidScheduleCalendarError):
        validate_day_hours(hours)


def test_a_whole_day_and_back_to_back_intervals_are_accepted():
    validate_day_hours(1440)
    validate_day_hours([WorkInterval(0, 720), WorkInterval(720, 720)])
    validate_weekly_hours(_week([WorkInterval(22 * 60, 480)]))
