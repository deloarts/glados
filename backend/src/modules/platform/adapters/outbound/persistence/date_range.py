"""
Translating calendar-date filter bounds into UTC timestamp bounds.

Event columns (`created`, `ordered_date`, `delivery_date`, ...) hold full
timestamps, but the filters over them are still calendar dates, the client
sends a date picker's value, not an instant. Comparing a timestamp against a
bare date makes the upper bound exclude the day it names: everything on
2026-08-06 after 00:00:00 sorts above `2026-08-06`, so an inclusive `<=` drops
the whole day.

These two helpers turn "from day X through day Y (inclusive)" into the
half-open interval `[X 00:00, Y+1 00:00)` that actually means that. The days
are read in `zone` and the bounds come back as UTC instants. Every filter a
user sets passes the tenant's timezone here (see tenant_zone.py); the UTC
default is for callers whose days are UTC days by definition.
"""

from datetime import UTC
from datetime import date
from datetime import datetime
from datetime import time
from datetime import timedelta
from datetime import tzinfo


def day_start_utc(day: date, zone: tzinfo = UTC) -> datetime:
    """First instant of `day` in `zone`, as UTC, the inclusive lower bound."""
    return datetime.combine(day, time.min, tzinfo=zone).astimezone(UTC)


def day_after_utc(day: date, zone: tzinfo = UTC) -> datetime:
    """First instant of the day AFTER `day` in `zone`, as UTC.

    Use with a strict `<` to include all of `day` itself.
    """
    return datetime.combine(day + timedelta(days=1), time.min, tzinfo=zone).astimezone(UTC)
