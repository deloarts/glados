"""
Centralises "now" so everything the app stores or stamps is UTC, not the
host's local time. In the production container TZ is UTC, so
`datetime.now()` and `datetime.now(UTC)` already agree there; the gap only
shows up in dev and tests, where the host can be in any timezone. Routing
every call through here keeps both environments behaving the same way and
gives a single place to patch when a caller needs a fixed clock in tests.
"""

from datetime import UTC
from datetime import date
from datetime import datetime
from datetime import timedelta
from datetime import tzinfo


def now_utc() -> datetime:
    """Return the current instant as a timezone-aware UTC datetime."""
    return datetime.now(UTC)


def as_utc(dt: datetime) -> datetime:
    """Normalize to timezone-aware UTC, reading a naive value as UTC."""
    return dt.replace(tzinfo=UTC) if dt.tzinfo is None else dt.astimezone(UTC)


def today_utc() -> date:
    """Return the current calendar date in UTC."""
    return now_utc().date()


def today_in(zone: tzinfo) -> date:
    """Return the current calendar date in `zone`, usually the tenant's
    timezone, the day every user sees and filters by."""
    return now_utc().astimezone(zone).date()


def start_of_iso_week(d: date) -> date:
    """Return the Monday of the ISO week that contains `d`."""
    return d - timedelta(days=d.weekday())
