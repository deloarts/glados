"""Totals computed from a fetched month journal: today's live figures, the
month's worked and target time, and one month's line of the year view.

Only days up to and including today count towards worked and target time,
so a running month is compared against the target accrued so far rather
than against the whole month. A closed day uses the worked time the system
reports; today's open day is computed live from its bookings; an earlier day
that was never closed counts its complete in/out pairs only.

Today's running balance is the system's figure once the day is closed;
while it is open, it is the latest reported balance before today plus
today's live day balance, and unknown when no earlier balance is in the
fetched range.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from datetime import datetime

from src.modules.operations.domain.services.time_tracking_time import is_clocked_in
from src.modules.operations.domain.services.time_tracking_time import target_reached_at
from src.modules.operations.domain.services.time_tracking_time import worked_seconds
from src.modules.operations.domain.value_objects.time_tracking import TimeTrackingBookingDirection
from src.modules.operations.domain.value_objects.time_tracking import TimeTrackingDay
from src.modules.operations.domain.value_objects.time_tracking import TimeTrackingMonth
from src.modules.operations.domain.value_objects.time_tracking import TimeTrackingYearMonth
from src.modules.operations.domain.value_objects.time_tracking import TimeTrackingYearSummary


@dataclass(frozen=True)
class TimeTrackingToday:
    day: date
    worked_seconds: int
    target_seconds: int
    day_balance_seconds: int
    running_balance_seconds: int | None
    clocked_in: bool
    first_in: datetime | None
    target_reached_at: datetime | None


@dataclass(frozen=True)
class TimeTrackingTotals:
    worked_seconds: int
    target_seconds: int
    balance_seconds: int


def day_worked_seconds(day: TimeTrackingDay, *, today: date, now: datetime) -> int | None:
    """Worked time of one day as the month table shows it."""
    if day.day == today and is_clocked_in(day.bookings):
        return worked_seconds(day.bookings, now)
    if day.worked_seconds is not None:
        return day.worked_seconds
    if day.day == today:
        return worked_seconds(day.bookings, now)
    if day.day < today and day.bookings:
        return worked_seconds(day.bookings)
    return None


def _latest_balance_before(days: Sequence[TimeTrackingDay], before: date) -> int | None:
    balance: int | None = None
    for day in sorted(days, key=lambda d: d.day):
        if day.day >= before:
            break
        if day.running_balance_seconds is not None:
            balance = day.running_balance_seconds
    return balance


def today_figures(
    month: TimeTrackingMonth, *, today: date, now: datetime
) -> TimeTrackingToday | None:
    """Live figures for today, or None when today is outside the month."""
    day = next((d for d in month.days if d.day == today), None)
    if day is None:
        return None
    clocked_in = is_clocked_in(day.bookings)
    worked = day_worked_seconds(day, today=today, now=now) or 0
    day_balance = worked - day.target_seconds
    if (
        not clocked_in
        and day.worked_seconds is not None
        and day.running_balance_seconds is not None
    ):
        running: int | None = day.running_balance_seconds
    else:
        previous = _latest_balance_before(month.days, today)
        running = previous + day_balance if previous is not None else None
    first_in = day.first_in or next(
        (
            b.at
            for b in sorted(day.bookings, key=lambda b: b.at)
            if b.direction is TimeTrackingBookingDirection.IN
        ),
        None,
    )
    return TimeTrackingToday(
        day=today,
        worked_seconds=worked,
        target_seconds=day.target_seconds,
        day_balance_seconds=day_balance,
        running_balance_seconds=running,
        clocked_in=clocked_in,
        first_in=first_in,
        target_reached_at=(
            target_reached_at(worked=worked, target=day.target_seconds, now=now)
            if clocked_in
            else None
        ),
    )


def month_totals(month: TimeTrackingMonth, *, today: date, now: datetime) -> TimeTrackingTotals:
    """Worked and target time of the days up to today, and their balance."""
    worked = 0
    target = 0
    for day in month.days:
        if day.day > today:
            continue
        worked += day_worked_seconds(day, today=today, now=now) or 0
        target += day.target_seconds
    return TimeTrackingTotals(
        worked_seconds=worked, target_seconds=target, balance_seconds=worked - target
    )


def year_month(month: TimeTrackingMonth, *, today: date, now: datetime) -> TimeTrackingYearMonth:
    """One line of the year view, with the last balance reported up to
    today as the month's end balance."""
    totals = month_totals(month, today=today, now=now)
    end_balance: int | None = None
    for day in sorted(month.days, key=lambda d: d.day):
        if day.day > today:
            break
        if day.running_balance_seconds is not None:
            end_balance = day.running_balance_seconds
    return TimeTrackingYearMonth(
        month=month.first_day.month,
        worked_seconds=totals.worked_seconds,
        target_seconds=totals.target_seconds,
        balance_seconds=totals.balance_seconds,
        end_balance_seconds=end_balance,
    )


def year_summary(year: int, months: Sequence[TimeTrackingYearMonth]) -> TimeTrackingYearSummary:
    """The year view: its months in order and the latest end balance."""
    ordered = tuple(sorted(months, key=lambda m: m.month))
    end_balance = next(
        (m.end_balance_seconds for m in reversed(ordered) if m.end_balance_seconds is not None),
        None,
    )
    return TimeTrackingYearSummary(year=year, months=ordered, end_balance_seconds=end_balance)
