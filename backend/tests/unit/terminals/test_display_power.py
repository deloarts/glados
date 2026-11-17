"""Display schedules and the display power of a terminal: schedule
validation, the power and its next change over window edges, midnight,
holidays and daylight saving changes, the manual override before, across
and after a schedule change, and terminals that are not approved."""

from datetime import UTC
from datetime import date
from datetime import datetime
from datetime import timedelta
from typing import Any
from zoneinfo import ZoneInfo

import pytest

from src.modules.operations.domain.entities.terminal import Terminal
from src.modules.operations.domain.errors import InvalidDisplayOverrideError
from src.modules.operations.domain.errors import InvalidInfoscreenConfigError
from src.modules.operations.domain.services import display_power_rules as rules
from src.modules.operations.domain.value_objects.display_schedule import WEEKDAYS
from src.modules.operations.domain.value_objects.display_schedule import DisplayCalendar
from src.modules.operations.domain.value_objects.display_schedule import DisplayPower
from src.modules.operations.domain.value_objects.display_schedule import DisplaySchedule
from src.modules.operations.domain.value_objects.display_schedule import DisplayScheduleDefault
from src.modules.operations.domain.value_objects.display_schedule import DisplayScheduleMode
from src.modules.operations.domain.value_objects.display_schedule import display_schedule_to_data
from src.modules.operations.domain.value_objects.display_schedule import parse_display_schedule
from src.modules.operations.domain.value_objects.terminal import TerminalMode
from src.modules.operations.domain.value_objects.terminal import TerminalStatus

VIENNA = ZoneInfo("Europe/Vienna")
CALENDAR = DisplayCalendar(zone=VIENNA, holidays=frozenset())


def _local(y: int, m: int, d: int, hh: int = 0, mm: int = 0) -> datetime:
    """A Vienna wall clock time as a UTC instant."""
    return datetime(y, m, d, hh, mm, tzinfo=VIENNA).astimezone(UTC)


def _weekdays(windows: list[dict[str, str]], weekend: list[dict[str, str]] | None = None) -> Any:
    raw: dict[str, Any] = {day: windows for day in WEEKDAYS[:5]}
    raw.update({day: weekend or [] for day in WEEKDAYS[5:]})
    return raw


def _schedule(raw: Any) -> DisplaySchedule:
    schedule = parse_display_schedule(raw)
    assert schedule is not None
    return schedule


OFFICE = _schedule(_weekdays([{"start": "07:00", "end": "18:00"}]))


def _terminal(**overrides: Any) -> Terminal:
    fields: dict[str, Any] = {
        "id": 1,
        "public_key": "k",
        "public_key_fingerprint": "0123456789abcdef",
        "status": TerminalStatus.APPROVED,
        "mode": TerminalMode.INFOSCREEN,
        "name": "Hall",
        "pairing_code": None,
        "pairing_expires_at": None,
        "infoscreen_id": 3,
        "api_key_id": None,
        "first_seen_at": datetime(2026, 1, 1, tzinfo=UTC),
        "last_seen_at": datetime(2026, 1, 1, tzinfo=UTC),
        "screen_display_schedule": OFFICE,
    }
    fields.update(overrides)
    return Terminal(**fields)


# ── Schedule validation ───────────────────────────────────────────────


def test_display_schedule_round_trips_and_sorts_windows() -> None:
    raw = {"monday": [{"start": "13:00", "end": "24:00"}, {"start": "00:00", "end": "06:30"}]}
    schedule = _schedule(raw)
    data = display_schedule_to_data(schedule)
    assert data is not None
    assert data["monday"] == [
        {"start": "00:00", "end": "06:30"},
        {"start": "13:00", "end": "24:00"},
    ]
    assert data["sunday"] == []
    assert parse_display_schedule(None) is None


@pytest.mark.parametrize(
    "raw",
    [
        {"monday": [{"start": "08:00", "end": "12:00"}, {"start": "11:00", "end": "13:00"}]},
        {"monday": [{"start": "12:00", "end": "08:00"}]},
        {"monday": [{"start": "08:00", "end": "08:00"}]},
        {"monday": [{"start": "24:00", "end": "24:00"}]},
        {"monday": [{"start": "8:00", "end": "12:00"}]},
        {"monday": [{"start": "08:60", "end": "12:00"}]},
        {"monday": [{"start": "08:00", "end": "24:01"}]},
        {"monday": [{"start": "08:00"}]},
        {"monday": "08:00-12:00"},
        {"funday": []},
        {"monday": [{"start": f"{h:02d}:00", "end": f"{h:02d}:30"} for h in range(7)]},
    ],
)
def test_display_schedule_refuses_invalid_windows(raw: Any) -> None:
    with pytest.raises(InvalidInfoscreenConfigError):
        parse_display_schedule(raw)


def test_display_schedule_allows_touching_windows() -> None:
    schedule = _schedule(
        {"monday": [{"start": "08:00", "end": "12:00"}, {"start": "12:00", "end": "13:00"}]}
    )
    assert len(schedule.days[0]) == 2


# ── Power from the schedule ───────────────────────────────────────────


def test_display_power_without_schedule_is_always_on() -> None:
    state = rules.schedule_state(None, False, CALENDAR, _local(2026, 11, 3, 3))
    assert (state.power, state.changes_at) == (DisplayPower.ON, None)


def test_display_power_at_the_window_edges() -> None:
    # Tuesday 2026-11-03.
    before = rules.schedule_state(OFFICE, False, CALENDAR, _local(2026, 11, 3, 6, 59))
    assert (before.power, before.changes_at) == ("off", _local(2026, 11, 3, 7))
    at_start = rules.schedule_state(OFFICE, False, CALENDAR, _local(2026, 11, 3, 7))
    assert (at_start.power, at_start.changes_at) == ("on", _local(2026, 11, 3, 18))
    at_end = rules.schedule_state(OFFICE, False, CALENDAR, _local(2026, 11, 3, 18))
    assert (at_end.power, at_end.changes_at) == ("off", _local(2026, 11, 4, 7))


def test_display_power_skips_the_weekend() -> None:
    friday_evening = rules.schedule_state(OFFICE, False, CALENDAR, _local(2026, 11, 6, 19))
    assert (friday_evening.power, friday_evening.changes_at) == ("off", _local(2026, 11, 9, 7))


def test_display_power_merges_windows_across_midnight() -> None:
    nights = _schedule(
        {
            day: [{"start": "00:00", "end": "06:00"}, {"start": "22:00", "end": "24:00"}]
            for day in WEEKDAYS
        }
    )
    late = rules.schedule_state(nights, False, CALENDAR, _local(2026, 11, 3, 23))
    assert (late.power, late.changes_at) == ("on", _local(2026, 11, 4, 6))


def test_display_power_always_on_schedule_foresees_no_change() -> None:
    always = _schedule({day: [{"start": "00:00", "end": "24:00"}] for day in WEEKDAYS})
    state = rules.schedule_state(always, False, CALENDAR, _local(2026, 11, 3, 12))
    assert (state.power, state.changes_at) == (DisplayPower.ON, None)


def test_display_power_schedule_without_windows_stays_off() -> None:
    state = rules.schedule_state(_schedule({}), False, CALENDAR, _local(2026, 11, 3, 12))
    assert (state.power, state.changes_at) == (DisplayPower.OFF, None)


def test_display_power_is_off_on_holidays_when_asked() -> None:
    calendar = DisplayCalendar(zone=VIENNA, holidays=frozenset({date(2026, 11, 4)}))
    evening = _local(2026, 11, 3, 19)
    with_holidays = rules.schedule_state(OFFICE, True, calendar, evening)
    assert with_holidays.changes_at == _local(2026, 11, 5, 7)
    noon = _local(2026, 11, 4, 12)
    assert rules.schedule_state(OFFICE, True, calendar, noon).power is DisplayPower.OFF
    assert rules.schedule_state(OFFICE, False, calendar, noon).power is DisplayPower.ON


def test_display_power_holiday_rule_without_schedule() -> None:
    calendar = DisplayCalendar(zone=VIENNA, holidays=frozenset({date(2026, 12, 25)}))
    state = rules.schedule_state(None, True, calendar, _local(2026, 12, 24, 12))
    assert (state.power, state.changes_at) == (DisplayPower.ON, _local(2026, 12, 25))
    state = rules.schedule_state(None, True, calendar, _local(2026, 12, 25, 12))
    assert (state.power, state.changes_at) == (DisplayPower.OFF, _local(2026, 12, 26))


def test_display_power_follows_wall_clock_across_daylight_saving_changes() -> None:
    # Vienna switches to summer time on Sunday 2026-03-29 and back on
    # Sunday 2026-10-25; the Monday window starts at 07:00 local either way.
    spring = rules.schedule_state(OFFICE, False, CALENDAR, _local(2026, 3, 27, 19))
    assert spring.changes_at == datetime(2026, 3, 30, 5, 0, tzinfo=UTC)
    autumn = rules.schedule_state(OFFICE, False, CALENDAR, _local(2026, 10, 23, 19))
    assert autumn.changes_at == datetime(2026, 10, 26, 6, 0, tzinfo=UTC)


def test_display_power_window_in_the_skipped_hour_still_starts() -> None:
    sunday_night = _schedule({"sunday": [{"start": "02:30", "end": "04:00"}]})
    state = rules.schedule_state(sunday_night, False, CALENDAR, _local(2026, 3, 28, 12))
    assert state.power is DisplayPower.OFF
    assert state.changes_at is not None
    assert (
        datetime(2026, 3, 29, 0, 0, tzinfo=UTC)
        < state.changes_at
        < datetime(2026, 3, 29, 2, 0, tzinfo=UTC)
    )


# ── Terminal power and the override ───────────────────────────────────


def test_display_power_of_a_terminal_that_is_not_approved_is_on() -> None:
    for status in (TerminalStatus.PENDING, TerminalStatus.REVOKED):
        terminal = _terminal(status=status, display_override=DisplayPower.OFF)
        state = rules.terminal_display_power(terminal, CALENDAR, _local(2026, 11, 3, 3))
        assert (state.power, state.changes_at) == (DisplayPower.ON, None)


def test_display_power_of_a_terminal_without_screen_ignores_the_schedule() -> None:
    terminal = _terminal(infoscreen_id=None)
    state = rules.terminal_display_power(terminal, CALENDAR, _local(2026, 11, 3, 3))
    assert (state.power, state.changes_at) == (DisplayPower.ON, None)


def test_display_power_override_until_the_next_schedule_change() -> None:
    now = _local(2026, 11, 3, 10)
    terminal = _terminal(
        display_override=DisplayPower.OFF, display_override_until=_local(2026, 11, 3, 18)
    )
    state = rules.terminal_display_power(terminal, CALENDAR, now)
    # At 18:00 the schedule says off too, so the display stays off until 07:00.
    assert (state.power, state.changes_at) == (DisplayPower.OFF, _local(2026, 11, 4, 7))


def test_display_power_override_ending_inside_a_window() -> None:
    now = _local(2026, 11, 3, 10)
    terminal = _terminal(
        display_override=DisplayPower.OFF, display_override_until=_local(2026, 11, 3, 12)
    )
    state = rules.terminal_display_power(terminal, CALENDAR, now)
    assert (state.power, state.changes_at) == (DisplayPower.OFF, _local(2026, 11, 3, 12))


def test_display_power_override_across_a_schedule_change() -> None:
    now = _local(2026, 11, 3, 17)
    terminal = _terminal(
        display_override=DisplayPower.ON, display_override_until=_local(2026, 11, 3, 20)
    )
    state = rules.terminal_display_power(terminal, CALENDAR, now)
    assert (state.power, state.changes_at) == (DisplayPower.ON, _local(2026, 11, 3, 20))


def test_display_power_ignores_an_override_that_ended() -> None:
    now = _local(2026, 11, 3, 21)
    terminal = _terminal(
        display_override=DisplayPower.ON, display_override_until=_local(2026, 11, 3, 20)
    )
    state = rules.terminal_display_power(terminal, CALENDAR, now)
    assert (state.power, state.changes_at) == (DisplayPower.OFF, _local(2026, 11, 4, 7))
    assert not rules.override_active(terminal, now)


def test_display_override_defaults_to_the_next_schedule_change() -> None:
    now = _local(2026, 11, 3, 10)
    assert rules.default_override_end(_terminal(), CALENDAR, now) == _local(2026, 11, 3, 18)
    assert rules.default_override_end(_terminal(infoscreen_id=None), CALENDAR, now) is None


def test_display_override_validation() -> None:
    now = datetime(2026, 11, 3, 10, tzinfo=UTC)
    terminal = _terminal()
    with pytest.raises(InvalidDisplayOverrideError):
        rules.set_override(terminal, DisplayPower.OFF, None, now)
    with pytest.raises(InvalidDisplayOverrideError):
        rules.set_override(terminal, DisplayPower.OFF, now, now)
    with pytest.raises(InvalidDisplayOverrideError):
        rules.set_override(terminal, DisplayPower.OFF, now + timedelta(days=32), now)
    rules.set_override(terminal, DisplayPower.OFF, now + timedelta(hours=1), now)
    assert (terminal.display_override, terminal.display_override_until) == (
        DisplayPower.OFF,
        now + timedelta(hours=1),
    )
    rules.clear_override(terminal)
    assert (terminal.display_override, terminal.display_override_until) == (None, None)


# ── Schedule mode and the default schedule ────────────────────────────

NIGHT_SHIFT = _schedule(_weekdays([{"start": "20:00", "end": "24:00"}]))
WITH_DEFAULT = DisplayCalendar(
    zone=VIENNA, holidays=frozenset(), default=DisplayScheduleDefault(schedule=NIGHT_SHIFT)
)
# A Wednesday at 10:00, inside the office hours and outside the night shift.
MORNING = _local(2026, 3, 11, 10)


def test_a_screen_following_the_default_uses_the_default_schedule() -> None:
    terminal = _terminal(screen_display_schedule_mode=DisplayScheduleMode.DEFAULT)
    state = rules.terminal_display_power(terminal, WITH_DEFAULT, MORNING)
    assert state.power == DisplayPower.OFF
    assert state.changes_at == _local(2026, 3, 11, 20)


def test_without_a_default_a_screen_following_it_is_always_on() -> None:
    terminal = _terminal(screen_display_schedule_mode=DisplayScheduleMode.DEFAULT)
    state = rules.terminal_display_power(terminal, CALENDAR, _local(2026, 3, 11, 22))
    assert (state.power, state.changes_at) == (DisplayPower.ON, None)


def test_the_default_holiday_switch_applies_to_screens_following_it() -> None:
    calendar = DisplayCalendar(
        zone=VIENNA,
        holidays=frozenset({date(2026, 3, 11)}),
        default=DisplayScheduleDefault(off_on_holidays=True),
    )
    terminal = _terminal(screen_display_schedule_mode=DisplayScheduleMode.DEFAULT)
    assert rules.terminal_display_power(terminal, calendar, MORNING).power == DisplayPower.OFF


def test_an_own_schedule_ignores_the_default() -> None:
    terminal = _terminal(screen_display_schedule_mode=DisplayScheduleMode.OWN)
    assert rules.terminal_display_power(terminal, WITH_DEFAULT, MORNING).power == DisplayPower.ON


def test_an_always_on_screen_ignores_both_schedules() -> None:
    terminal = _terminal(screen_display_schedule_mode=DisplayScheduleMode.ALWAYS_ON)
    state = rules.terminal_display_power(terminal, WITH_DEFAULT, _local(2026, 3, 11, 6))
    assert (state.power, state.changes_at) == (DisplayPower.ON, None)


def test_a_terminal_without_a_screen_does_not_follow_the_default() -> None:
    terminal = _terminal(
        infoscreen_id=None, screen_display_schedule_mode=DisplayScheduleMode.DEFAULT
    )
    state = rules.terminal_display_power(terminal, WITH_DEFAULT, MORNING)
    assert (state.power, state.changes_at) == (DisplayPower.ON, None)
