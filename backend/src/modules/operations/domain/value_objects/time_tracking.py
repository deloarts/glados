"""
Provider-neutral read model of attendance data fetched from a time tracking
system. These values live only for the request that fetched them and are
never persisted. Durations are whole seconds and datetimes are UTC-aware.

The time tracking provider port hands them to the application layer, and the
summary services in domain/services compute totals from them, which is why
they sit in the domain rather than next to the port.
"""

from dataclasses import dataclass
from datetime import date
from datetime import datetime
from enum import StrEnum


class TimeTrackingBookingDirection(StrEnum):
    IN = "in"
    OUT = "out"


class TimeTrackingDayStatus(StrEnum):
    NORMAL = "normal"
    SHIFT_FREE = "shift_free"
    HOLIDAY = "holiday"
    ABSENCE = "absence"
    OPEN = "open"


class TimeTrackingAccountFormat(StrEnum):
    """How an account's values are written. Durations are seconds, shown as
    h:mm (`duration_clock`) or as decimal hours (`duration_hours`); `count`
    is a whole number, `decimal` a number with two places, `money` an amount
    in cents, and `raw` a number without a known format."""

    DURATION_CLOCK = "duration_clock"
    DURATION_HOURS = "duration_hours"
    COUNT = "count"
    DECIMAL = "decimal"
    MONEY = "money"
    RAW = "raw"


@dataclass(frozen=True)
class TimeTrackingBooking:
    at: datetime
    direction: TimeTrackingBookingDirection


@dataclass(frozen=True)
class TimeTrackingDay:
    """One day of a month. `worked_seconds` is None while the day is still
    open; `running_balance_seconds` is the balance after the day as the
    system reports it, None when it reports none. Shift names are None for
    a system without shifts."""

    day: date
    shift_name: str | None
    shift_short_name: str | None
    target_seconds: int
    worked_seconds: int | None
    running_balance_seconds: int | None
    first_in: datetime | None
    last_out: datetime | None
    status: TimeTrackingDayStatus
    bookings: tuple[TimeTrackingBooking, ...]


@dataclass(frozen=True)
class TimeTrackingAccount:
    """One account (balance, vacation, sickness, surcharges, whatever the
    instance configures), with its value before, during and after the
    month. `format` tells how to render the values."""

    account_id: int
    name: str
    short_name: str
    format: TimeTrackingAccountFormat
    pre: float
    sum: float
    post: float


@dataclass(frozen=True)
class TimeTrackingMonth:
    first_day: date
    last_day: date
    days: tuple[TimeTrackingDay, ...]
    accounts: tuple[TimeTrackingAccount, ...]


@dataclass(frozen=True)
class TimeTrackingYearMonth:
    month: int
    worked_seconds: int
    target_seconds: int
    balance_seconds: int
    end_balance_seconds: int | None


@dataclass(frozen=True)
class TimeTrackingYearSummary:
    year: int
    months: tuple[TimeTrackingYearMonth, ...]
    end_balance_seconds: int | None


@dataclass(frozen=True)
class TimeTrackingReadRights:
    """What the user's own account may read: single days, a month, a year.
    None means that right was not checked for this response."""

    days: bool | None
    month: bool | None
    year: bool | None
