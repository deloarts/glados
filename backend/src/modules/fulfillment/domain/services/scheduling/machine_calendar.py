"""Machine calendars and the placement of working time on them.

A day's working time is a list of intervals, each a start in the tenant's
local time and a length in minutes of at most a whole day. An interval
belongs to the local day it starts on, also when it runs past midnight, and
it is converted to UTC with that day's offset, so a calendar keeps its local
hours across a daylight saving change. A day may also be given as a plain
minute count, which means one interval from DEFAULT_DAY_START_MINUTE.

A machine's own week overrides the admin default week, a tenant holiday
closes the day under both, and a machine's calendar exception replaces the
day whatever the week or the holidays say. Downtimes are blocked spans cut
out of the working windows (apply_downtimes). place() is the only primitive
that turns a duration into a planned window.
"""

from collections.abc import Iterable
from collections.abc import Iterator
from collections.abc import Mapping
from collections.abc import Sequence
from dataclasses import dataclass
from dataclasses import field
from dataclasses import replace
from datetime import UTC
from datetime import date
from datetime import datetime
from datetime import time
from datetime import timedelta
from datetime import tzinfo
from itertools import pairwise

from src.modules.fulfillment.domain.entities.machine_downtime import MachineDowntime
from src.modules.fulfillment.domain.errors import NoWorkingTimeError
from src.modules.fulfillment.domain.value_objects.work_interval import DEFAULT_DAY_START_MINUTE
from src.modules.fulfillment.domain.value_objects.work_interval import MINUTES_PER_DAY
from src.modules.fulfillment.domain.value_objects.work_interval import DayHours
from src.modules.fulfillment.domain.value_objects.work_interval import WorkInterval
from src.modules.fulfillment.domain.value_objects.work_interval import day_intervals
from src.modules.platform.domain.exceptions import InvalidScheduleCalendarError
from src.shared_kernel.domain.services.clock import as_utc

# About ten years of calendar days, a defensive bound never expected to hit.
_SEARCH_DAYS = 3660

type Window = tuple[datetime, datetime]


def validate_day_hours(hours: DayHours) -> None:
    """Every start lies within the day, every length is between 0 and a
    whole day, and the intervals of one day neither overlap nor add up to
    more than a whole day."""
    intervals = (
        [WorkInterval(DEFAULT_DAY_START_MINUTE, hours)] if isinstance(hours, int) else list(hours)
    )
    for interval in intervals:
        if not 0 <= interval.start_minute < MINUTES_PER_DAY:
            raise InvalidScheduleCalendarError("A working interval must start within its day.")
        if not 0 <= interval.minutes <= MINUTES_PER_DAY:
            raise InvalidScheduleCalendarError(
                f"A working interval must last between 0 and {MINUTES_PER_DAY} minutes."
            )
    ordered = sorted(intervals, key=lambda i: i.start_minute)
    for earlier, later in pairwise(ordered):
        if earlier.start_minute + earlier.minutes > later.start_minute:
            raise InvalidScheduleCalendarError("The working intervals of a day must not overlap.")
    if sum(i.minutes for i in intervals) > MINUTES_PER_DAY:
        raise InvalidScheduleCalendarError(
            f"A day cannot hold more than {MINUTES_PER_DAY} working minutes."
        )


def validate_weekly_hours(weekly_hours: Mapping[int, DayHours]) -> None:
    """weekday keys must be exactly 0..6 (Monday..Sunday, matches
    date.weekday()), each day valid per validate_day_hours."""
    if set(weekly_hours.keys()) != set(range(7)):
        raise InvalidScheduleCalendarError(
            "Weekly hours must specify all 7 weekdays (0=Monday..6=Sunday)."
        )
    for hours in weekly_hours.values():
        validate_day_hours(hours)


def resolve_weekly_minutes(
    default_weekly_hours: Mapping[int, DayHours],
    machine_weekly_hours: Mapping[int, DayHours] | None,
) -> dict[int, DayHours]:
    """A machine's own MachineWorkingHours.weekly_minutes overrides the
    global AdminProductionSettings.default_weekly_hours when present."""
    if machine_weekly_hours is not None:
        return dict(machine_weekly_hours)
    return dict(default_weekly_hours)


@dataclass(frozen=True)
class MachineCalendar:
    """The fully resolved calendar for one machine: the weekly template, the
    tenant holidays, the per-date exceptions on top, the tenant zone the
    hours are local to, and the blocked spans (UTC, sorted) cut out of the
    resulting windows."""

    weekly: dict[int, tuple[WorkInterval, ...]]
    exceptions: dict[date, tuple[WorkInterval, ...]]
    zone: tzinfo = UTC
    holidays: frozenset[date] = frozenset()
    blocked: tuple[Window, ...] = ()
    # Windows per local day, filled on first use; replace() starts it empty.
    _windows: dict[date, tuple[Window, ...]] = field(
        default_factory=dict, init=False, repr=False, compare=False
    )

    def intervals_on(self, d: date) -> tuple[WorkInterval, ...]:
        if d in self.exceptions:
            return self.exceptions[d]
        if d in self.holidays:
            return ()
        return self.weekly.get(d.weekday(), ())

    def windows_on(self, d: date) -> tuple[Window, ...]:
        """The UTC windows of the intervals that start on local day `d`,
        less the blocked spans, in start order."""
        cached = self._windows.get(d)
        if cached is None:
            cached = tuple(
                piece
                for interval in self.intervals_on(d)
                for piece in _subtract(self._interval_window(d, interval), self.blocked)
            )
            self._windows[d] = cached
        return cached

    def minutes_available_on(self, d: date) -> int:
        return round(sum((end - start).total_seconds() for start, end in self.windows_on(d)) / 60)

    def windows_from(self, moment: datetime) -> Iterator[Window]:
        """The working windows that end after `moment`, in time order, with
        windows that touch or overlap merged. Raises NoWorkingTimeError
        when none is found within the search bound."""
        moment = as_utc(moment)
        # A window of the previous local day can still be running.
        day = moment.astimezone(self.zone).date() - timedelta(days=1)
        pending: Window | None = None
        for offset in range(_SEARCH_DAYS):
            for start, end in self.windows_on(day + timedelta(days=offset)):
                if pending is not None and start <= pending[1]:
                    pending = (pending[0], max(pending[1], end))
                    continue
                if pending is not None and pending[1] > moment:
                    yield pending
                pending = (start, end)
        if pending is not None and pending[1] > moment:
            yield pending
        raise NoWorkingTimeError(
            "No working time found within 10 years of the requested start, check the calendar."
        )

    def _interval_window(self, d: date, interval: WorkInterval) -> Window:
        local_start = datetime.combine(
            d, time(interval.start_minute // 60, interval.start_minute % 60), tzinfo=self.zone
        )
        start = local_start.astimezone(UTC)
        return start, start + timedelta(minutes=interval.minutes)


def _subtract(window: Window, blocked: Sequence[Window]) -> list[Window]:
    """`window` less every blocked span, as the pieces that remain."""
    pieces = [window]
    for block_start, block_end in blocked:
        if block_start >= window[1]:
            break
        remaining: list[Window] = []
        for start, end in pieces:
            if block_end <= start or block_start >= end:
                remaining.append((start, end))
                continue
            if start < block_start:
                remaining.append((start, block_start))
            if block_end < end:
                remaining.append((block_end, end))
        pieces = remaining
    return pieces


def build_machine_calendar(
    default_weekly_hours: Mapping[int, DayHours],
    machine_weekly_hours: Mapping[int, DayHours] | None,
    exception_hours_by_date: Mapping[date, DayHours],
    *,
    zone: tzinfo = UTC,
    holidays: Iterable[date] = (),
) -> MachineCalendar:
    weekly = resolve_weekly_minutes(default_weekly_hours, machine_weekly_hours)
    return MachineCalendar(
        weekly={weekday: day_intervals(hours) for weekday, hours in weekly.items()},
        exceptions={d: day_intervals(hours) for d, hours in exception_hours_by_date.items()},
        zone=zone,
        holidays=frozenset(holidays),
    )


def snap_to_working_start(dt: datetime, calendar: MachineCalendar) -> datetime:
    """Rolls dt forward to the next moment inside a working window."""
    moment = as_utc(dt)
    for start, _end in calendar.windows_from(moment):
        return max(start, moment)
    raise AssertionError("windows_from raises rather than running out")


def place(
    earliest: datetime, duration_minutes: int, calendar: MachineCalendar
) -> tuple[datetime, datetime]:
    """Places a block of working time starting no earlier than `earliest`
    and returns (planned_start, planned_end). A 0-minute duration still
    snaps its start to a valid working moment."""
    moment = as_utc(earliest)
    remaining = float(duration_minutes)
    planned_start: datetime | None = None
    for window_start, window_end in calendar.windows_from(moment):
        start = max(window_start, moment)
        if planned_start is None:
            planned_start = start
        available = (window_end - start).total_seconds() / 60
        if remaining <= available:
            return planned_start, start + timedelta(minutes=remaining)
        remaining -= available
    raise AssertionError("windows_from raises rather than running out")


def apply_downtimes(
    calendar: MachineCalendar, downtimes: Iterable[MachineDowntime], now: datetime
) -> MachineCalendar:
    """Cuts the downtimes out of the calendar's working windows.

    An open downtime blocks the rest of the local day it is in from its
    start, today for one already running, since an ongoing breakdown gives
    no signal for when it ends. Downtimes that have already ended are
    ignored, so history never changes planning capacity. The calendar comes
    back unchanged when no downtime touches working time."""
    now = as_utc(now)
    local_today = now.astimezone(calendar.zone).date()
    today_start = datetime.combine(local_today, time.min, tzinfo=calendar.zone).astimezone(UTC)
    spans = [
        span
        for downtime in downtimes
        if (span := _downtime_span(downtime, now, today_start, calendar.zone)) is not None
        and _touches_working_time(calendar, span)
    ]
    if not spans:
        return calendar
    return replace(calendar, blocked=_merged([*calendar.blocked, *spans]))


def _downtime_span(
    downtime: MachineDowntime, now: datetime, today_start: datetime, zone: tzinfo
) -> Window | None:
    """Clips one downtime to today or later, or returns None when nothing
    of it remains."""
    span_start = max(as_utc(downtime.started_at), today_start)
    if downtime.ended_at is None:
        start_day = span_start.astimezone(zone).date()
        span_end = datetime.combine(
            start_day + timedelta(days=1), time.min, tzinfo=zone
        ).astimezone(UTC)
    else:
        span_end = as_utc(downtime.ended_at)
        if span_end <= now:
            return None
    if span_end <= span_start:
        return None
    return span_start, span_end


def _touches_working_time(calendar: MachineCalendar, span: Window) -> bool:
    first = span[0].astimezone(calendar.zone).date() - timedelta(days=1)
    last = span[1].astimezone(calendar.zone).date()
    for offset in range((last - first).days + 1):
        for start, end in calendar.windows_on(first + timedelta(days=offset)):
            if start < span[1] and span[0] < end:
                return True
    return False


def _merged(spans: Iterable[Window]) -> tuple[Window, ...]:
    merged: list[Window] = []
    for start, end in sorted(spans):
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    return tuple(merged)
