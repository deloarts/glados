"""When the displays of an infoscreen are switched on, and the manual
override a terminal can carry on top of that.

A schedule lists, per weekday, the windows in which the display is on, as
wall clock times of the tenant timezone. A window runs from its start to
its end on the same day; `24:00` ends it at midnight, so a display that runs
through the night gets one window ending at midnight and one starting at
midnight on the next day. A weekday without windows is off all day. A
screen without a schedule is always on.

A screen's mode says which schedule its displays follow: the default
schedule of the installation, its own, or none at all. The default is set
once for every screen that follows it, and without one they are always on.

The schedule is stored as one JSON column. `parse_display_schedule` turns
that JSON (or a request dumped to plain data) into these value objects and
refuses anything the rules do not allow; `display_schedule_to_data` turns
them back into plain data.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from datetime import datetime
from datetime import timedelta
from datetime import tzinfo
from enum import unique
from itertools import pairwise
from typing import Any
from typing import Final

from src.modules.operations.domain.errors import InvalidInfoscreenConfigError
from src.shared_kernel.domain.value_objects.value_enum import StrValueEnum


@unique
class DisplayPower(StrValueEnum):
    ON = "on"
    OFF = "off"


@unique
class DisplayScheduleMode(StrValueEnum):
    DEFAULT = "default"
    OWN = "own"
    ALWAYS_ON = "always_on"


# Monday first, the order of date.weekday().
WEEKDAYS: Final = (
    "monday",
    "tuesday",
    "wednesday",
    "thursday",
    "friday",
    "saturday",
    "sunday",
)
MAX_WINDOWS_PER_DAY: Final = 6
MINUTES_PER_DAY: Final = 24 * 60
# How far an override may reach into the future.
MAX_OVERRIDE_DURATION: Final = timedelta(days=31)


@dataclass(frozen=True)
class DisplayWindow:
    """An on-window of one day, in minutes after local midnight. `end` is
    exclusive and may be 1440, the following midnight."""

    start: int
    end: int


@dataclass(frozen=True)
class DisplaySchedule:
    """One tuple of windows per weekday, Monday first, each sorted by start."""

    days: tuple[tuple[DisplayWindow, ...], ...]

    def windows_on(self, day: date) -> tuple[DisplayWindow, ...]:
        return self.days[day.weekday()]


@dataclass(frozen=True)
class DisplayScheduleDefault:
    """The schedule the screens in the Default mode follow. No schedule
    keeps their displays on, except on holidays when the switch says so."""

    schedule: DisplaySchedule | None = None
    off_on_holidays: bool = False


@dataclass(frozen=True)
class DisplayCalendar:
    """What a schedule is read against: the tenant timezone, the days of the
    tenant holidays and the default schedule."""

    zone: tzinfo
    holidays: frozenset[date]
    default: DisplayScheduleDefault = DisplayScheduleDefault()


@dataclass(frozen=True)
class DisplayPowerState:
    """Whether the display is on, and when that changes next. None means no
    change is foreseen within the horizon the rules look at."""

    power: DisplayPower
    changes_at: datetime | None


def _fail(message: str) -> InvalidInfoscreenConfigError:
    return InvalidInfoscreenConfigError(f"Display schedule: {message}")


def _minutes(value: Any, where: str, *, is_end: bool) -> int:
    """`HH:MM` as minutes after midnight. A start runs from 00:00 to 23:59,
    an end from 00:01 to 24:00."""
    if not isinstance(value, str) or len(value) != 5 or value[2] != ":":
        raise _fail(f"{where} must be a time like 07:30.")
    hours, minutes = value[:2], value[3:]
    if not (hours.isdigit() and minutes.isdigit()):
        raise _fail(f"{where} must be a time like 07:30.")
    total = int(hours) * 60 + int(minutes)
    if int(minutes) > 59 or total > MINUTES_PER_DAY or (total == MINUTES_PER_DAY and not is_end):
        raise _fail(f"{where} must lie between 00:00 and 24:00.")
    return total


def _day(raw: Any, weekday: str) -> tuple[DisplayWindow, ...]:
    if raw is None:
        return ()
    if not isinstance(raw, list | tuple):
        raise _fail(f"{weekday} must be a list of windows.")
    if len(raw) > MAX_WINDOWS_PER_DAY:
        raise _fail(f"{weekday} may have at most {MAX_WINDOWS_PER_DAY} windows.")
    windows: list[DisplayWindow] = []
    for raw_window in raw:
        if not isinstance(raw_window, Mapping):
            raise _fail(f"a window of {weekday} needs a start and an end.")
        start = _minutes(raw_window.get("start"), f"the start of a {weekday} window", is_end=False)
        end = _minutes(raw_window.get("end"), f"the end of a {weekday} window", is_end=True)
        if end <= start:
            raise _fail(f"a {weekday} window must end after it starts.")
        windows.append(DisplayWindow(start=start, end=end))
    windows.sort(key=lambda w: w.start)
    for before, after in pairwise(windows):
        if after.start < before.end:
            raise _fail(f"the windows of {weekday} overlap.")
    return tuple(windows)


def parse_display_schedule(raw: Mapping[str, Any] | None) -> DisplaySchedule | None:
    """A schedule from plain data, None for no schedule. Every weekday key is
    optional and means a day without windows when left out; unknown keys
    are refused."""
    if raw is None:
        return None
    if not isinstance(raw, Mapping):
        raise _fail("must be an object with one list of windows per weekday.")
    unknown = sorted(set(raw) - set(WEEKDAYS))
    if unknown:
        raise _fail(f"unknown weekday(s) {unknown}.")
    return DisplaySchedule(days=tuple(_day(raw.get(day), day) for day in WEEKDAYS))


def _hhmm(minutes: int) -> str:
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def display_schedule_to_data(schedule: DisplaySchedule | None) -> dict[str, Any] | None:
    """Plain data of a schedule, the shape parse_display_schedule reads."""
    if schedule is None:
        return None
    return {
        weekday: [{"start": _hhmm(w.start), "end": _hhmm(w.end)} for w in windows]
        for weekday, windows in zip(WEEKDAYS, schedule.days, strict=True)
    }
