"""
Expands a created_from/created_to/changed_from/changed_to query filter value into a UTC,
timezone-aware datetime bound. A full datetime is used as given (a naive one is treated as
UTC); a date-only value stands for the whole calendar day in the given zone, which is the
tenant's default timezone from the general settings, the one timezone the whole app reads
calendar days in.
"""

from datetime import UTC
from datetime import date
from datetime import datetime
from datetime import time
from datetime import tzinfo
from zoneinfo import ZoneInfo
from zoneinfo import ZoneInfoNotFoundError


def resolve_actor_timezone(tz_name: str) -> ZoneInfo:
    """Best-effort resolution of an IANA timezone name, such as the tenant's default
    timezone, UTC on any lookup failure (unknown name, empty string)."""
    try:
        return ZoneInfo(tz_name)
    except (ZoneInfoNotFoundError, ValueError):
        return ZoneInfo("UTC")


def expand_date_filter(value: date | datetime, zone: tzinfo, *, end_of_day: bool) -> datetime:
    """Normalizes one filter value to a UTC datetime bound. `end_of_day` picks the start
    (`created_from`/`changed_from`) or the end (`created_to`/`changed_to`) of the calendar
    day in `zone` when `value` carries no time component."""
    if isinstance(value, datetime):
        return value if value.tzinfo is not None else value.replace(tzinfo=UTC)

    local = datetime.combine(value, time.max if end_of_day else time.min, tzinfo=zone)
    return local.astimezone(UTC)
