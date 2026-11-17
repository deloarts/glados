"""
Unit tests for scheduling.apply_downtimes: layering machine
downtime windows on top of an already-resolved MachineCalendar as blocked
spans cut out of its working windows. No database, no HTTP, pure functions
only.
"""

from datetime import UTC
from datetime import datetime

from src.modules.fulfillment.domain.entities.machine_downtime import MachineDowntime
from src.modules.fulfillment.domain.services.scheduling import apply_downtimes
from src.modules.fulfillment.domain.services.scheduling import build_machine_calendar
from src.modules.fulfillment.domain.value_objects.machine_downtime_reason import (
    MachineDowntimeReason,
)
from tests.unit.scheduling_service._helpers import MONDAY
from tests.unit.scheduling_service._helpers import TUESDAY
from tests.unit.scheduling_service._helpers import WEEKDAY_HOURS


def make_downtime(
    machine_id: int = 1,
    started_at: datetime = datetime(2026, 7, 27, 9, 0, tzinfo=UTC),
    ended_at: datetime | None = None,
) -> MachineDowntime:
    return MachineDowntime(
        id=1,
        created=started_at,
        changed=None,
        changes=[],
        machine_id=machine_id,
        started_at=started_at,
        ended_at=ended_at,
        reason=MachineDowntimeReason.BREAKDOWN,
        note=None,
        reported_by_id=1,
        ended_by_id=None,
    )


def make_calendar():
    # Mon-Fri 8h shift starting at 08:00 (the default day start), weekend
    # off, matching WEEKDAY_HOURS's own 480-minutes-on-weekdays shape.
    return build_machine_calendar(WEEKDAY_HOURS, None, {})


def test_open_downtime_today_zeros_the_rest_of_the_shift():
    # Machine went down at 10:00 on Monday, still open; "now" is 11:00 the
    # same day. Working window is 08:00-16:00 (480 minutes), so only the
    # first 2 hours (08:00-10:00) survive; the rest of today is written
    # off regardless of the exact minute "now" falls on.
    calendar = make_calendar()
    downtime = make_downtime(started_at=datetime(2026, 7, 27, 10, 0, tzinfo=UTC), ended_at=None)
    now = datetime(2026, 7, 27, 11, 0, tzinfo=UTC)

    result = apply_downtimes(calendar, [downtime], now)

    assert result.minutes_available_on(MONDAY) == 120
    # Tomorrow is untouched: an open downtime never projects past today.
    assert result.minutes_available_on(TUESDAY) == 480


def test_open_downtime_that_started_before_today_zeros_all_of_today():
    # A breakdown that has been open since last week still only writes off
    # today, not the days already past, since downtime history isn't re-applied.
    calendar = make_calendar()
    downtime = make_downtime(started_at=datetime(2026, 7, 20, 9, 0, tzinfo=UTC), ended_at=None)
    now = datetime(2026, 7, 27, 14, 0, tzinfo=UTC)

    result = apply_downtimes(calendar, [downtime], now)

    assert result.minutes_available_on(MONDAY) == 0
    assert result.minutes_available_on(TUESDAY) == 480


def test_closed_downtime_spanning_two_days():
    # Started Monday 22:00 (after the 08:00-16:00 shift already ended, so
    # Monday itself is untouched), ends Tuesday 10:00 (2 hours into
    # Tuesday's shift).
    calendar = make_calendar()
    downtime = make_downtime(
        started_at=datetime(2026, 7, 27, 22, 0, tzinfo=UTC),
        ended_at=datetime(2026, 7, 28, 10, 0, tzinfo=UTC),
    )
    now = datetime(2026, 7, 27, 8, 0, tzinfo=UTC)

    result = apply_downtimes(calendar, [downtime], now)

    assert result.minutes_available_on(MONDAY) == 480
    assert result.minutes_available_on(TUESDAY) == 360  # 480 - 120
    # The lost time is the start of the shift, not its end.
    assert result.windows_on(TUESDAY) == (
        (datetime(2026, 7, 28, 10, 0, tzinfo=UTC), datetime(2026, 7, 28, 16, 0, tzinfo=UTC)),
    )


def test_closed_downtime_fully_outside_working_hours_changes_nothing():
    calendar = make_calendar()
    downtime = make_downtime(
        started_at=datetime(2026, 7, 27, 18, 0, tzinfo=UTC),
        ended_at=datetime(2026, 7, 27, 20, 0, tzinfo=UTC),
    )
    now = datetime(2026, 7, 27, 8, 0, tzinfo=UTC)

    result = apply_downtimes(calendar, [downtime], now)

    assert result is calendar  # unchanged input returned verbatim, no copy needed


def test_downtime_covering_the_whole_day_yields_a_zero_minute_exception():
    calendar = make_calendar()
    downtime = make_downtime(
        started_at=datetime(2026, 7, 27, 0, 0, tzinfo=UTC),
        ended_at=datetime(2026, 7, 28, 0, 0, tzinfo=UTC),
    )
    now = datetime(2026, 7, 27, 8, 0, tzinfo=UTC)

    result = apply_downtimes(calendar, [downtime], now)

    assert result.minutes_available_on(MONDAY) == 0


def test_future_planned_maintenance_reduces_only_its_own_day():
    # A closed downtime entirely in the future (planned maintenance booked
    # ahead of time) is applied exactly like any other closed window.
    calendar = make_calendar()
    downtime = make_downtime(
        started_at=datetime(2026, 8, 3, 9, 0, tzinfo=UTC),  # a Monday
        ended_at=datetime(2026, 8, 3, 13, 0, tzinfo=UTC),
    )
    now = datetime(2026, 7, 27, 8, 0, tzinfo=UTC)

    result = apply_downtimes(calendar, [downtime], now)

    assert result.minutes_available_on(downtime.started_at.date()) == 240
    assert result.minutes_available_on(MONDAY) == 480


def test_downtime_entirely_in_the_past_changes_nothing():
    # Downtime history never changes planning capacity: a closed window
    # that both started and ended before today is simply irrelevant here.
    calendar = make_calendar()
    downtime = make_downtime(
        started_at=datetime(2026, 7, 20, 9, 0, tzinfo=UTC),
        ended_at=datetime(2026, 7, 20, 13, 0, tzinfo=UTC),
    )
    now = datetime(2026, 7, 27, 8, 0, tzinfo=UTC)

    result = apply_downtimes(calendar, [downtime], now)

    assert result is calendar


def test_multiple_downtimes_on_the_same_day_accumulate():
    calendar = make_calendar()
    downtimes = [
        make_downtime(
            started_at=datetime(2026, 7, 27, 8, 0, tzinfo=UTC),
            ended_at=datetime(2026, 7, 27, 9, 0, tzinfo=UTC),
        ),
        make_downtime(
            started_at=datetime(2026, 7, 27, 13, 0, tzinfo=UTC),
            ended_at=datetime(2026, 7, 27, 14, 0, tzinfo=UTC),
        ),
    ]
    now = datetime(2026, 7, 27, 7, 0, tzinfo=UTC)

    result = apply_downtimes(calendar, downtimes, now)

    assert result.minutes_available_on(MONDAY) == 360  # 480 - 60 - 60


def test_no_downtimes_returns_the_calendar_unchanged():
    calendar = make_calendar()
    now = datetime(2026, 7, 27, 8, 0, tzinfo=UTC)

    result = apply_downtimes(calendar, [], now)

    assert result is calendar


def test_existing_calendar_exception_is_respected_as_the_baseline():
    # A day already reduced by a calendar exception (e.g. a half-day
    # holiday) gets the downtime overlap subtracted from that reduced
    # figure, not from the full weekly template.
    calendar = build_machine_calendar(WEEKDAY_HOURS, None, {MONDAY: 240})
    downtime = make_downtime(
        started_at=datetime(2026, 7, 27, 8, 0, tzinfo=UTC),
        ended_at=datetime(2026, 7, 27, 9, 0, tzinfo=UTC),
    )
    now = datetime(2026, 7, 27, 7, 0, tzinfo=UTC)

    result = apply_downtimes(calendar, [downtime], now)

    assert result.minutes_available_on(MONDAY) == 180  # 240 - 60


def test_an_open_downtime_reported_ahead_blocks_its_own_day_from_its_start():
    # Reported on Monday for Tuesday 12:00 with no end yet: Monday keeps its
    # shift, and Tuesday is written off from noon, as a breakdown then would.
    calendar = make_calendar()
    downtime = make_downtime(started_at=datetime(2026, 7, 28, 12, 0, tzinfo=UTC), ended_at=None)
    now = datetime(2026, 7, 27, 11, 0, tzinfo=UTC)

    result = apply_downtimes(calendar, [downtime], now)

    assert result.minutes_available_on(MONDAY) == 480
    assert result.minutes_available_on(TUESDAY) == 240
