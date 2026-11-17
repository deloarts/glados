"""
Pydantic wire models for the answers of the time tracking service, the
contract Glados defines in docs/reference/time-tracking-provider.md. Every
model ignores fields it does not name, so a service that adds fields
changes nothing here, and carries a `to_*` method converting it into the
domain's value objects and the port's dataclasses, so nothing outside this
package sees the wire shape. An account format Glados does not know reads
as `raw`.
"""

from datetime import date
from datetime import datetime
from typing import Literal

from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import field_validator

from src.modules.operations.domain.value_objects.time_tracking import TimeTrackingAccount
from src.modules.operations.domain.value_objects.time_tracking import TimeTrackingAccountFormat
from src.modules.operations.domain.value_objects.time_tracking import TimeTrackingBooking
from src.modules.operations.domain.value_objects.time_tracking import TimeTrackingBookingDirection
from src.modules.operations.domain.value_objects.time_tracking import TimeTrackingDay
from src.modules.operations.domain.value_objects.time_tracking import TimeTrackingDayStatus
from src.modules.operations.domain.value_objects.time_tracking import TimeTrackingMonth
from src.modules.operations.domain.value_objects.time_tracking import TimeTrackingReadRights
from src.modules.operations.ports.outbound.time_tracking_provider_port import (
    TimeTrackingCredentialField,
)
from src.modules.operations.ports.outbound.time_tracking_provider_port import TimeTrackingMonthRead
from src.modules.operations.ports.outbound.time_tracking_provider_port import (
    TimeTrackingServiceInfo,
)
from src.modules.operations.ports.outbound.time_tracking_provider_port import (
    TimeTrackingServiceStatus,
)
from src.modules.operations.ports.outbound.time_tracking_provider_port import (
    TimeTrackingVerification,
)
from src.modules.operations.ports.outbound.time_tracking_provider_port import TimeTrackingYearRead


class _WireModel(BaseModel):
    model_config = ConfigDict(extra="ignore")


class ErrorBody(_WireModel):
    code: str = ""
    message: str = ""


class Health(_WireModel):
    version: str


class CredentialField(_WireModel):
    name: str
    kind: Literal["text", "secret"]
    required: bool
    max_length: int


class Info(_WireModel):
    service: str
    version: str
    contract_version: str
    provider_label: str
    credential_fields: list[CredentialField]
    credential_public_key: str
    credential_key_id: str
    binding: str

    def to_info(self) -> TimeTrackingServiceInfo:
        return TimeTrackingServiceInfo(
            service=self.service,
            version=self.version,
            contract_version=self.contract_version,
            provider_label=self.provider_label,
            credential_fields=tuple(
                TimeTrackingCredentialField(
                    name=f.name, kind=f.kind, required=f.required, max_length=f.max_length
                )
                for f in self.credential_fields
            ),
            credential_public_key=self.credential_public_key,
            credential_key_id=self.credential_key_id,
            binding=self.binding,
        )


class Status(_WireModel):
    server_version: str
    default_project: str

    def to_status(self) -> TimeTrackingServiceStatus:
        return TimeTrackingServiceStatus(
            server_version=self.server_version, default_project=self.default_project
        )


class Rights(_WireModel):
    days: bool
    month: bool
    year: bool

    def to_rights(self) -> TimeTrackingReadRights:
        return TimeTrackingReadRights(days=self.days, month=self.month, year=self.year)


class Verification(_WireModel):
    binding: str
    employee_name: str
    rights: Rights

    def to_verification(self) -> TimeTrackingVerification:
        return TimeTrackingVerification(
            binding=self.binding, employee_name=self.employee_name, rights=self.rights.to_rights()
        )


class Booking(_WireModel):
    at: datetime
    direction: TimeTrackingBookingDirection

    @field_validator("at")
    @classmethod
    def _aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("booking times must carry an offset")
        return value


class Day(_WireModel):
    date: date
    shift_name: str | None = None
    shift_short_name: str | None = None
    target_seconds: int
    worked_seconds: int | None
    running_balance_seconds: int | None = None
    first_in: datetime | None
    last_out: datetime | None
    status: TimeTrackingDayStatus
    bookings: list[Booking]

    def to_day(self) -> TimeTrackingDay:
        return TimeTrackingDay(
            day=self.date,
            shift_name=self.shift_name,
            shift_short_name=self.shift_short_name,
            target_seconds=self.target_seconds,
            worked_seconds=self.worked_seconds,
            running_balance_seconds=self.running_balance_seconds,
            first_in=self.first_in,
            last_out=self.last_out,
            status=self.status,
            bookings=tuple(
                TimeTrackingBooking(at=b.at, direction=b.direction)
                for b in sorted(self.bookings, key=lambda b: b.at)
            ),
        )


class Account(_WireModel):
    account_id: int
    name: str
    short_name: str
    format: str
    pre: float
    sum: float
    post: float

    def to_account(self) -> TimeTrackingAccount:
        try:
            value_format = TimeTrackingAccountFormat(self.format)
        except ValueError:
            value_format = TimeTrackingAccountFormat.RAW
        return TimeTrackingAccount(
            account_id=self.account_id,
            name=self.name,
            short_name=self.short_name,
            format=value_format,
            pre=self.pre,
            sum=self.sum,
            post=self.post,
        )


class Month(_WireModel):
    first_day: date
    last_day: date
    days: list[Day]
    accounts: list[Account]

    def to_month(self) -> TimeTrackingMonth:
        return TimeTrackingMonth(
            first_day=self.first_day,
            last_day=self.last_day,
            days=tuple(sorted((d.to_day() for d in self.days), key=lambda d: d.day)),
            accounts=tuple(a.to_account() for a in self.accounts),
        )


class MonthAnswer(_WireModel):
    employee_name: str
    month: Month
    fetched_at: datetime

    def to_read(self) -> TimeTrackingMonthRead:
        return TimeTrackingMonthRead(
            employee_name=self.employee_name,
            month=self.month.to_month(),
            fetched_at=self.fetched_at,
        )


class YearAnswer(_WireModel):
    employee_name: str
    months: list[Month]
    fetched_at: datetime

    def to_read(self) -> TimeTrackingYearRead:
        return TimeTrackingYearRead(
            employee_name=self.employee_name,
            months=tuple(m.to_month() for m in self.months),
            fetched_at=self.fetched_at,
        )
