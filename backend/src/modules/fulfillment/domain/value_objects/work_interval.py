"""Working time within one day of a calendar.

A WorkInterval starts at a local time, given as minutes after local
midnight, and lasts a number of minutes of at most a whole day. A day's
hours are a list of intervals, or a plain minute count, which stands for
one interval from DEFAULT_DAY_START_MINUTE. The clock form "HH:MM" is how
the API writes a start.
"""

import re
from collections.abc import Sequence
from dataclasses import dataclass

MINUTES_PER_DAY = 1440
DEFAULT_DAY_START_MINUTE = 8 * 60
CLOCK_PATTERN = r"^([01]\d|2[0-3]):[0-5]\d$"


@dataclass(frozen=True)
class WorkInterval:
    """Working time that starts `start_minute` minutes after local midnight
    and lasts `minutes`."""

    start_minute: int
    minutes: int

    @property
    def start_clock(self) -> str:
        return f"{self.start_minute // 60:02d}:{self.start_minute % 60:02d}"


# A day's hours: a minute count from DEFAULT_DAY_START_MINUTE, or intervals.
type DayHours = int | Sequence[WorkInterval]


def clock_minute(clock: str) -> int:
    """The minutes after midnight of an "HH:MM" clock time."""
    if not re.match(CLOCK_PATTERN, clock):
        raise ValueError(f"{clock!r} is not a time of day in HH:MM form.")
    hours, minutes = clock.split(":")
    return int(hours) * 60 + int(minutes)


def day_intervals(hours: DayHours) -> tuple[WorkInterval, ...]:
    """The intervals a day's hours stand for, in start order, without
    empty ones."""
    if isinstance(hours, int):
        return (WorkInterval(DEFAULT_DAY_START_MINUTE, hours),) if hours > 0 else ()
    return tuple(sorted((i for i in hours if i.minutes > 0), key=lambda i: i.start_minute))
