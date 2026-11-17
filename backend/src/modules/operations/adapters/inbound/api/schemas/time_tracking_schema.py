"""
HTTP schemas for the user's own time tracking surfaces. The password is a
SecretStr and the time tracking routes never echo request input in a
validation error, so it cannot come back in a 422 body. Responses carry no
password, only whether one is configured, and the fetched journal data is
returned for this request only.
"""

from datetime import date
from datetime import datetime

from pydantic import BaseModel
from pydantic import Field
from pydantic import SecretStr
from pydantic import field_validator

from src.modules.operations.domain.services.time_tracking_rules import PASSWORD_MAX_LENGTH
from src.modules.operations.domain.services.time_tracking_rules import USER_MAX_LENGTH
from src.modules.operations.domain.services.time_tracking_rules import CredentialsInvalidReason
from src.modules.operations.domain.services.time_tracking_rules import (
    validate_time_tracking_password,
)
from src.modules.operations.domain.services.time_tracking_rules import validate_time_tracking_user
from src.modules.operations.domain.value_objects.time_tracking import TimeTrackingAccountFormat
from src.modules.operations.domain.value_objects.time_tracking import TimeTrackingDayStatus
from src.modules.platform.adapters.inbound.api.schemas.base import ResponseModel


class SaveTimeTrackingCredentialsRequest(BaseModel):
    """Omitting the password, or sending null or "", keeps the stored one.
    `time_tracking_consent_version` must be the version the user just
    confirmed in the consent dialog."""

    time_tracking_user: str = Field(max_length=USER_MAX_LENGTH)
    time_tracking_password: SecretStr | None = Field(default=None, max_length=PASSWORD_MAX_LENGTH)
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


class TimeTrackingReadRightsResponse(ResponseModel):
    """What the account may read (single days, a month, a year); null when
    not checked."""

    days: bool | None
    month: bool | None
    year: bool | None


class TimeTrackingAccountResponse(ResponseModel):
    time_tracking_user: str | None
    time_tracking_password_configured: bool
    time_tracking_credentials_valid: bool
    time_tracking_credentials_invalid_reason: CredentialsInvalidReason | None
    # The consent text version a save must confirm.
    time_tracking_consent_version: int
    time_tracking_consent_current: bool
    time_tracking_privacy_policy_url: str | None
    # The name of the time tracking system, as the service reports it.
    time_tracking_provider_label: str | None
    time_tracking_employee_name: str | None
    time_tracking_rights: TimeTrackingReadRightsResponse | None


class TimeTrackingBookingResponse(ResponseModel):
    at: datetime
    # "in" or "out"
    direction: str


class TimeTrackingDayResponse(ResponseModel):
    date: date
    # ISO weekday, 1 is Monday.
    weekday: int
    shift_name: str | None
    shift_short_name: str | None
    first_in: datetime | None
    last_out: datetime | None
    bookings: list[TimeTrackingBookingResponse]
    worked_seconds: int | None
    target_seconds: int
    day_balance_seconds: int | None
    running_balance_seconds: int | None
    status: TimeTrackingDayStatus


class TimeTrackingAccountValueResponse(ResponseModel):
    account_id: int
    name: str
    short_name: str
    format: TimeTrackingAccountFormat
    pre: float
    sum: float
    post: float


class TimeTrackingTodayResponse(ResponseModel):
    date: date
    worked_seconds: int
    target_seconds: int
    day_balance_seconds: int
    running_balance_seconds: int | None
    clocked_in: bool
    first_in: datetime | None
    target_reached_at: datetime | None


class TimeTrackingTotalsResponse(ResponseModel):
    today: TimeTrackingTodayResponse | None
    worked_seconds: int
    target_seconds: int
    balance_seconds: int


class TimeTrackingMonthResponse(ResponseModel):
    month: str
    first_day: date
    last_day: date
    employee_name: str
    days: list[TimeTrackingDayResponse]
    accounts: list[TimeTrackingAccountValueResponse]
    totals: TimeTrackingTotalsResponse | None
    rights: TimeTrackingReadRightsResponse
    fetched_at: datetime


class TimeTrackingYearMonthResponse(ResponseModel):
    month: int
    worked_seconds: int
    target_seconds: int
    balance_seconds: int
    end_balance_seconds: int | None


class TimeTrackingYearResponse(ResponseModel):
    year: int
    employee_name: str
    months: list[TimeTrackingYearMonthResponse]
    end_balance_seconds: int | None
    rights: TimeTrackingReadRightsResponse
    fetched_at: datetime
