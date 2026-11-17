"""Time arithmetic for attendance data read from a time tracking system.
Stamps arrive in UTC; the time tracking service converts the system's own
wall-clock values before they reach Glados.

Worked time is computed the way the time tracking system computes it:
every stamp is truncated to the minute before the in/out pairs are
subtracted, so a live "worked so far" figure for an open day matches the
system's own figure once the day is closed.
"""

from collections.abc import Sequence
from datetime import datetime
from datetime import timedelta

from src.modules.operations.domain.value_objects.time_tracking import TimeTrackingBooking
from src.modules.operations.domain.value_objects.time_tracking import TimeTrackingBookingDirection


def truncate_to_minute(value: datetime) -> datetime:
    return value.replace(second=0, microsecond=0)


def worked_seconds(bookings: Sequence[TimeTrackingBooking], now: datetime | None = None) -> int:
    """Sum of the closed in/out pairs on minute-truncated stamps, plus the
    open interval up to `now` (also truncated) when the last booking is an
    "in" and `now` is given. A second "in" without an "out" in between keeps
    the first one; an "out" without a preceding "in" is ignored."""
    total = timedelta()
    open_since: datetime | None = None
    for booking in sorted(bookings, key=lambda b: b.at):
        stamp = truncate_to_minute(booking.at)
        if booking.direction is TimeTrackingBookingDirection.IN:
            if open_since is None:
                open_since = stamp
        elif open_since is not None:
            total += max(stamp - open_since, timedelta())
            open_since = None
    if open_since is not None and now is not None:
        total += max(truncate_to_minute(now) - open_since, timedelta())
    return int(total.total_seconds())


def is_clocked_in(bookings: Sequence[TimeTrackingBooking]) -> bool:
    """Whether the latest booking is an "in"."""
    if not bookings:
        return False
    latest = max(bookings, key=lambda b: b.at)
    return latest.direction is TimeTrackingBookingDirection.IN


def target_reached_at(*, worked: int, target: int, now: datetime) -> datetime | None:
    """When the day's target is (or was) reached while clocked in: now plus
    the time still missing, minute-truncated. None without a target."""
    if target <= 0:
        return None
    return truncate_to_minute(now) + timedelta(seconds=target - worked)
