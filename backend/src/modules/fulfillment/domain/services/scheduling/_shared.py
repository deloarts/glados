"""Date helpers shared by the scheduling modules.

Stored instants are timezone-aware UTC, and every datetime entering the
walk goes through `as_utc` from the clock module, because comparing a naive
day window with an aware database timestamp raises a TypeError. Calendar
days are the tenant's: an instant is reduced to the day it falls on in the
tenant's timezone, and a day starts at the tenant's local midnight. The
zone is always passed in, so no conversion silently falls back to UTC.
"""

from datetime import UTC
from datetime import date
from datetime import datetime
from datetime import time
from datetime import tzinfo

from src.shared_kernel.domain.services.clock import as_utc


def day_start(d: date, zone: tzinfo) -> datetime:
    """The UTC instant at which day `d` begins in `zone`, its local
    midnight with that day's own offset."""
    return datetime.combine(d, time.min, tzinfo=zone).astimezone(UTC)


def day_of(moment: datetime, zone: tzinfo) -> date:
    """The day in `zone` that `moment` falls on. A naive value is read as
    UTC."""
    return as_utc(moment).astimezone(zone).date()


def as_day(value: date | datetime | None, zone: tzinfo) -> date | None:
    """Reduces an instant to the day it falls on in `zone` and passes a
    plain date through. `datetime` subclasses `date`, so a stray timestamp
    type-checks but fails on the first comparison; normalizing here avoids
    that."""
    if isinstance(value, datetime):
        return day_of(value, zone)
    return value
