"""
Commands and results for the user's own time tracking surfaces: stored
credentials and their state, and the month and year views. The password is
a SecretStr, so it never shows up in a repr, a log line or a validation
error, and no result carries it. Results hold data fetched for one request
only; nothing here is persisted.
"""

from datetime import date
from datetime import datetime

from pydantic import BaseModel
from pydantic import SecretStr
from pydantic import field_validator

from src.modules.operations.domain.services.time_tracking_rules import (
    validate_time_tracking_password,
)
from src.modules.operations.domain.services.time_tracking_rules import validate_time_tracking_user


class SaveTimeTrackingCredentialsCommand(BaseModel):
    """None for the password re-verifies the stored credentials, which only
    works for the same user name. Validators mirror
    SaveTimeTrackingCredentialsRequest."""

    time_tracking_user: str
    time_tracking_password: SecretStr | None = None
    time_tracking_consent_version: int | None = None

    @field_validator("time_tracking_user")
    @classmethod
    def _user(cls, value: str) -> str:
        return validate_time_tracking_user(value)

    @field_validator("time_tracking_password")
    @classmethod
    def _password(cls, value: SecretStr | None) -> SecretStr | None:
        if value is None or not value.get_secret_value():
            return None
        validate_time_tracking_password(value.get_secret_value())
        return value


class TimeTrackingReadRightsResult(BaseModel):
    days: bool | None
    month: bool | None
    year: bool | None


class TimeTrackingAccountResult(BaseModel):
    """The user's own stored credentials and whether they can be used,
    from Glados state alone. Employee name and rights are only present
    right after a save or an access check."""

    time_tracking_user: str | None
    time_tracking_password_configured: bool
    time_tracking_credentials_valid: bool
    time_tracking_credentials_invalid_reason: str | None
    time_tracking_consent_version: int
    time_tracking_consent_current: bool
    time_tracking_privacy_policy_url: str | None
    time_tracking_provider_label: str | None
    time_tracking_employee_name: str | None = None
    time_tracking_rights: TimeTrackingReadRightsResult | None = None


class TimeTrackingBookingResult(BaseModel):
    at: datetime
    direction: str


class TimeTrackingDayResult(BaseModel):
    date: date
    weekday: int
    shift_name: str | None
    shift_short_name: str | None
    first_in: datetime | None
    last_out: datetime | None
    bookings: list[TimeTrackingBookingResult]
    worked_seconds: int | None
    target_seconds: int
    day_balance_seconds: int | None
    running_balance_seconds: int | None
    status: str


class TimeTrackingAccountValueResult(BaseModel):
    account_id: int
    name: str
    short_name: str
    format: str
    pre: float
    sum: float
    post: float


class TimeTrackingTodayResult(BaseModel):
    date: date
    worked_seconds: int
    target_seconds: int
    day_balance_seconds: int
    running_balance_seconds: int | None
    clocked_in: bool
    first_in: datetime | None
    target_reached_at: datetime | None


class TimeTrackingTotalsResult(BaseModel):
    today: TimeTrackingTodayResult | None
    worked_seconds: int
    target_seconds: int
    balance_seconds: int


class TimeTrackingMonthResult(BaseModel):
    month: str
    first_day: date
    last_day: date
    employee_name: str
    days: list[TimeTrackingDayResult]
    accounts: list[TimeTrackingAccountValueResult]
    totals: TimeTrackingTotalsResult | None
    rights: TimeTrackingReadRightsResult
    fetched_at: datetime


class TimeTrackingYearMonthResult(BaseModel):
    month: int
    worked_seconds: int
    target_seconds: int
    balance_seconds: int
    end_balance_seconds: int | None


class TimeTrackingYearResult(BaseModel):
    year: int
    employee_name: str
    months: list[TimeTrackingYearMonthResult]
    end_balance_seconds: int | None
    rights: TimeTrackingReadRightsResult
    fetched_at: datetime
