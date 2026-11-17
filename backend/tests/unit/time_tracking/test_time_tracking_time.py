"""
The time arithmetic behind the time tracking view
(domain/services/time_tracking_time.py) and the totals built on it
(domain/services/time_tracking_summary.py): minute truncation, live worked time of an
open day, the time the target is reached, and the month and year totals.
"""

from datetime import UTC
from datetime import date
from datetime import datetime

from src.modules.operations.domain.services.time_tracking_summary import day_worked_seconds
from src.modules.operations.domain.services.time_tracking_summary import month_totals
from src.modules.operations.domain.services.time_tracking_summary import today_figures
from src.modules.operations.domain.services.time_tracking_summary import year_month
from src.modules.operations.domain.services.time_tracking_summary import year_summary
from src.modules.operations.domain.services.time_tracking_time import is_clocked_in
from src.modules.operations.domain.services.time_tracking_time import target_reached_at
from src.modules.operations.domain.services.time_tracking_time import truncate_to_minute
from src.modules.operations.domain.services.time_tracking_time import worked_seconds
from src.modules.operations.domain.value_objects.time_tracking import TimeTrackingBooking
from src.modules.operations.domain.value_objects.time_tracking import TimeTrackingBookingDirection
from src.modules.operations.domain.value_objects.time_tracking import TimeTrackingDay
from src.modules.operations.domain.value_objects.time_tracking import TimeTrackingDayStatus
from src.modules.operations.domain.value_objects.time_tracking import TimeTrackingMonth
from src.modules.operations.domain.value_objects.time_tracking import TimeTrackingYearMonth

IN = TimeTrackingBookingDirection.IN
OUT = TimeTrackingBookingDirection.OUT


def utc(*args: int) -> datetime:
    return datetime(*args, tzinfo=UTC)  # type: ignore[misc]


def booking(at: datetime, direction: TimeTrackingBookingDirection) -> TimeTrackingBooking:
    return TimeTrackingBooking(at=at, direction=direction)


def make_day(
    day: date,
    *,
    target: int = 27720,
    worked: int | None = None,
    balance: int | None = None,
    bookings: tuple[TimeTrackingBooking, ...] = (),
    status: TimeTrackingDayStatus = TimeTrackingDayStatus.NORMAL,
) -> TimeTrackingDay:
    return TimeTrackingDay(
        day=day,
        shift_name="Full time 38.5h",
        shift_short_name="FT",
        target_seconds=target,
        worked_seconds=worked,
        running_balance_seconds=balance,
        first_in=None,
        last_out=None,
        status=status,
        bookings=bookings,
    )


# ── minute truncation and worked time ────────────────────────────────


def test_truncate_to_minute() -> None:
    assert truncate_to_minute(utc(2026, 9, 29, 6, 43, 59)) == utc(2026, 9, 29, 6, 43)


def test_closed_pairs_use_minute_truncated_stamps() -> None:
    bookings = (
        booking(utc(2026, 9, 29, 6, 43, 19), IN),
        booking(utc(2026, 9, 29, 15, 3, 35), OUT),
    )
    # 08:43 to 17:03 counts as 8:20, the seconds are dropped on both ends.
    assert worked_seconds(bookings) == 30000


def test_open_day_counts_up_to_now_truncated() -> None:
    bookings = (
        booking(utc(2026, 9, 30, 5, 58, 12), IN),
        booking(utc(2026, 9, 30, 9, 0, 40), OUT),
        booking(utc(2026, 9, 30, 9, 30, 5), IN),
    )
    now = utc(2026, 9, 30, 10, 15, 59)

    assert worked_seconds(bookings, now) == (3 * 3600 + 2 * 60) + 45 * 60
    assert worked_seconds(bookings) == 3 * 3600 + 2 * 60
    assert is_clocked_in(bookings)


def test_repeated_in_keeps_the_first_and_stray_out_is_ignored() -> None:
    bookings = (
        booking(utc(2026, 9, 30, 5, 0), OUT),
        booking(utc(2026, 9, 30, 6, 0), IN),
        booking(utc(2026, 9, 30, 7, 0), IN),
        booking(utc(2026, 9, 30, 8, 0), OUT),
    )
    assert worked_seconds(bookings) == 2 * 3600
    assert not is_clocked_in(bookings)


def test_target_reached_at_projects_from_now() -> None:
    now = utc(2026, 9, 30, 8, 15, 59)

    assert target_reached_at(worked=8220, target=27720, now=now) == utc(2026, 9, 30, 13, 40)
    assert target_reached_at(worked=28000, target=27720, now=now) == utc(2026, 9, 30, 8, 10, 20)
    assert target_reached_at(worked=100, target=0, now=now) is None


# ── summaries ────────────────────────────────────────────────────────


def september(today_bookings: tuple[TimeTrackingBooking, ...]) -> TimeTrackingMonth:
    return TimeTrackingMonth(
        first_day=date(2026, 9, 1),
        last_day=date(2026, 9, 30),
        days=(
            make_day(date(2026, 9, 27), target=0, balance=3600),
            make_day(date(2026, 9, 28), worked=27720, balance=3600),
            make_day(date(2026, 9, 29), worked=30000, balance=5880),
            make_day(date(2026, 9, 30), bookings=today_bookings),
        ),
        accounts=(),
    )


def test_today_figures_while_clocked_in() -> None:
    month = september((booking(utc(2026, 9, 30, 5, 58, 12), IN),))
    now = utc(2026, 9, 30, 8, 15, 59)

    today = today_figures(month, today=date(2026, 9, 30), now=now)

    assert today is not None
    assert today.clocked_in
    assert today.worked_seconds == 2 * 3600 + 17 * 60
    assert today.day_balance_seconds == today.worked_seconds - 27720
    assert today.running_balance_seconds == 5880 + today.day_balance_seconds
    assert today.first_in == utc(2026, 9, 30, 5, 58, 12)
    assert today.target_reached_at == utc(2026, 9, 30, 13, 40)


def test_today_figures_outside_the_month_is_none() -> None:
    month = september(())
    assert today_figures(month, today=date(2026, 10, 6), now=utc(2026, 10, 6, 8, 0)) is None


def test_month_totals_only_count_days_up_to_today() -> None:
    month = september((booking(utc(2026, 9, 30, 5, 58), IN),))
    now = utc(2026, 9, 30, 6, 58)

    running = month_totals(month, today=date(2026, 9, 29), now=now)
    full = month_totals(month, today=date(2026, 9, 30), now=now)

    assert (running.worked_seconds, running.target_seconds) == (57720, 2 * 27720)
    assert running.balance_seconds == 57720 - 2 * 27720
    assert full.worked_seconds == 57720 + 3600
    assert full.target_seconds == 3 * 27720


def test_unclosed_past_day_counts_complete_pairs_only() -> None:
    day = make_day(
        date(2026, 9, 2),
        bookings=(
            booking(utc(2026, 9, 2, 6, 0), IN),
            booking(utc(2026, 9, 2, 7, 0), OUT),
            booking(utc(2026, 9, 2, 8, 0), IN),
        ),
    )
    assert day_worked_seconds(day, today=date(2026, 9, 30), now=utc(2026, 9, 30, 8)) == 3600


def test_year_month_and_summary() -> None:
    month = september(())
    line = year_month(month, today=date(2026, 9, 30), now=utc(2026, 9, 30, 20))

    assert line.month == 9
    assert line.end_balance_seconds == 5880
    summary = year_summary(
        2026,
        [
            line,
            TimeTrackingYearMonth(8, 100, 50, 50, 1200),
            TimeTrackingYearMonth(10, 0, 0, 0, None),
        ],
    )
    assert [m.month for m in summary.months] == [8, 9, 10]
    assert summary.end_balance_seconds == 5880
