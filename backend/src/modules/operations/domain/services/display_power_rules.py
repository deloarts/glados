"""
Whether a terminal's display is on right now and when that changes next.
No I/O.

Glados decides and the device executes: the device state carries the power
and the moment it changes, and the display asks again at that moment, so no
scheduler runs on the server. The schedule of the screen a terminal shows
decides, or the default schedule when the screen follows it, read in the
tenant timezone with its holidays. A manual override on
the terminal wins until it ends, after which the schedule applies again.
Only an approved terminal follows either; a pending or revoked one shows a
waiting screen and stays on.

The schedule's wall clock windows become instants day by day, so a day with
a daylight saving change has the length it really has. Windows that touch
across midnight merge into one stretch, so a display running through the
night reports one change in the morning rather than one at midnight. The
rules look two weeks ahead; a display whose power does not change within
that horizon gets no change time and picks up a later change through its
regular state polling.
"""

from datetime import UTC
from datetime import date
from datetime import datetime
from datetime import time
from datetime import timedelta
from datetime import tzinfo

from src.modules.operations.domain.entities.terminal import Terminal
from src.modules.operations.domain.errors import InvalidDisplayOverrideError
from src.modules.operations.domain.value_objects.display_schedule import MAX_OVERRIDE_DURATION
from src.modules.operations.domain.value_objects.display_schedule import DisplayCalendar
from src.modules.operations.domain.value_objects.display_schedule import DisplayPower
from src.modules.operations.domain.value_objects.display_schedule import DisplayPowerState
from src.modules.operations.domain.value_objects.display_schedule import DisplaySchedule
from src.modules.operations.domain.value_objects.display_schedule import DisplayScheduleMode
from src.modules.operations.domain.value_objects.terminal import TerminalStatus

HORIZON_DAYS = 14

_ON = DisplayPower.ON
_OFF = DisplayPower.OFF

Interval = tuple[datetime, datetime]


def _local_instant(day: date, minutes: int, zone: tzinfo) -> datetime:
    """The UTC instant of a wall clock time on a local day. 1440 minutes is
    the following midnight. A time that a daylight saving change skips is
    read with the offset before the change."""
    if minutes >= 24 * 60:
        day, minutes = day + timedelta(days=1), minutes - 24 * 60
    return datetime.combine(day, time(minutes // 60, minutes % 60), tzinfo=zone).astimezone(UTC)


def _day_intervals(
    schedule: DisplaySchedule | None,
    off_on_holidays: bool,
    calendar: DisplayCalendar,
    day: date,
) -> list[Interval]:
    if off_on_holidays and day in calendar.holidays:
        return []
    if schedule is None:
        return [(_local_instant(day, 0, calendar.zone), _local_instant(day, 1440, calendar.zone))]
    return [
        (_local_instant(day, w.start, calendar.zone), _local_instant(day, w.end, calendar.zone))
        for w in schedule.windows_on(day)
    ]


def _merged(intervals: list[Interval]) -> list[Interval]:
    merged: list[Interval] = []
    for start, end in sorted(intervals):
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    return merged


def schedule_state(
    schedule: DisplaySchedule | None,
    off_on_holidays: bool,
    calendar: DisplayCalendar,
    at: datetime,
) -> DisplayPowerState:
    """The power the schedule gives at `at`, and its next change within the
    horizon. No schedule and no holiday rule means always on."""
    if schedule is None and not off_on_holidays:
        return DisplayPowerState(power=_ON, changes_at=None)
    today = at.astimezone(calendar.zone).date()
    first = today - timedelta(days=1)
    days = [first + timedelta(days=offset) for offset in range(HORIZON_DAYS + 2)]
    horizon_end = _local_instant(days[-1], 1440, calendar.zone)
    on = _merged(
        [
            interval
            for day in days
            for interval in _day_intervals(schedule, off_on_holidays, calendar, day)
        ]
    )
    for start, end in on:
        if start <= at < end:
            return DisplayPowerState(power=_ON, changes_at=end if end < horizon_end else None)
        if start > at:
            return DisplayPowerState(power=_OFF, changes_at=start)
    return DisplayPowerState(power=_OFF, changes_at=None)


def _followed_schedule(
    terminal: Terminal, calendar: DisplayCalendar
) -> tuple[DisplaySchedule | None, bool]:
    """The schedule and holiday switch the terminal's display follows: none
    without a screen or for an always on screen, the default for a screen
    that follows it, otherwise the screen's own."""
    if terminal.infoscreen_id is None:
        return None, False
    mode = terminal.screen_display_schedule_mode
    if mode == DisplayScheduleMode.ALWAYS_ON:
        return None, False
    if mode == DisplayScheduleMode.DEFAULT:
        return calendar.default.schedule, calendar.default.off_on_holidays
    return terminal.screen_display_schedule, terminal.screen_off_on_holidays


def override_active(terminal: Terminal, now: datetime) -> bool:
    return (
        terminal.display_override is not None
        and terminal.display_override_until is not None
        and now < terminal.display_override_until
    )


def terminal_display_power(
    terminal: Terminal, calendar: DisplayCalendar, now: datetime
) -> DisplayPowerState:
    """The power of the terminal's display at `now` and its next change. The
    override holds until it ends; the schedule of the shown screen applies
    before and after it."""
    if terminal.status != TerminalStatus.APPROVED:
        return DisplayPowerState(power=_ON, changes_at=None)
    schedule, off_on_holidays = _followed_schedule(terminal, calendar)
    forced = terminal.display_override
    until = terminal.display_override_until
    if forced is None or until is None or not override_active(terminal, now):
        return schedule_state(schedule, off_on_holidays, calendar, now)
    after = schedule_state(schedule, off_on_holidays, calendar, until)
    if after.power != forced:
        return DisplayPowerState(power=forced, changes_at=until)
    return DisplayPowerState(power=forced, changes_at=after.changes_at)


def default_override_end(
    terminal: Terminal, calendar: DisplayCalendar, now: datetime
) -> datetime | None:
    """When an override set now ends unless an end is given: the next
    change of the schedule, None when none is foreseen."""
    schedule, off_on_holidays = _followed_schedule(terminal, calendar)
    return schedule_state(schedule, off_on_holidays, calendar, now).changes_at


def set_override(
    terminal: Terminal, power: DisplayPower, until: datetime | None, now: datetime
) -> None:
    """Forces the display on or off until the given moment, which must lie
    in the future and at most the maximum override duration ahead."""
    if until is None:
        raise InvalidDisplayOverrideError(
            "The screen's schedule has no upcoming change, so the override needs an end."
        )
    if until <= now:
        raise InvalidDisplayOverrideError("The override must end in the future.")
    if until > now + MAX_OVERRIDE_DURATION:
        raise InvalidDisplayOverrideError(
            f"The override may last at most {MAX_OVERRIDE_DURATION.days} days."
        )
    terminal.display_override = power
    terminal.display_override_until = until


def clear_override(terminal: Terminal) -> None:
    terminal.display_override = None
    terminal.display_override_until = None
