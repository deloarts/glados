"""
Pure validation for a machine downtime's time window: a range must end
strictly after it starts, and a machine may never have two downtime
windows that overlap in time. No I/O, no ORM.
"""

from datetime import UTC
from datetime import datetime

# Sentinel standing in for "still ongoing, no known end" when comparing an
# open window against another window for overlap. An open window blocks
# any other window that starts after it, not just ones up to "now": a
# machine that is currently down indefinitely cannot also have a second,
# future downtime window recorded on top of it.
_UNBOUNDED_END = datetime.max.replace(tzinfo=UTC)


def is_valid_range(started_at: datetime, ended_at: datetime | None) -> bool:
    """A range is valid when open (ended_at is None) or when it ends
    strictly after it starts."""
    return ended_at is None or ended_at > started_at


def windows_overlap(
    a_start: datetime, a_end: datetime | None, b_start: datetime, b_end: datetime | None
) -> bool:
    """True when two [start, end) windows share any instant. An open
    window (end None) is treated as extending indefinitely into the
    future for this comparison."""
    a_end_effective = a_end or _UNBOUNDED_END
    b_end_effective = b_end or _UNBOUNDED_END
    return a_start < b_end_effective and b_start < a_end_effective
