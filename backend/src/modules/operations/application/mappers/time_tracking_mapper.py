"""
Builds the time tracking result DTOs: the account state from stored Glados
data, and the month and year views from freshly fetched months plus the
totals the domain summary services compute. The password never reaches a
result, only whether one is configured.
"""

from datetime import date
from datetime import datetime

from src.modules.operations.application.dto.time_tracking_dto import TimeTrackingAccountResult
from src.modules.operations.application.dto.time_tracking_dto import TimeTrackingAccountValueResult
from src.modules.operations.application.dto.time_tracking_dto import TimeTrackingBookingResult
from src.modules.operations.application.dto.time_tracking_dto import TimeTrackingDayResult
from src.modules.operations.application.dto.time_tracking_dto import TimeTrackingMonthResult
from src.modules.operations.application.dto.time_tracking_dto import TimeTrackingReadRightsResult
from src.modules.operations.application.dto.time_tracking_dto import TimeTrackingTodayResult
from src.modules.operations.application.dto.time_tracking_dto import TimeTrackingTotalsResult
from src.modules.operations.application.dto.time_tracking_dto import TimeTrackingYearMonthResult
from src.modules.operations.application.dto.time_tracking_dto import TimeTrackingYearResult
from src.modules.operations.domain.entities.admin_settings.time_tracking import (
    AdminTimeTrackingSettings,
)
from src.modules.operations.domain.entities.user_time_tracking_credentials import (
    UserTimeTrackingCredentials,
)
from src.modules.operations.domain.services.time_tracking_rules import TIME_TRACKING_CONSENT_VERSION
from src.modules.operations.domain.services.time_tracking_rules import credentials_invalid_reason
from src.modules.operations.domain.services.time_tracking_summary import day_worked_seconds
from src.modules.operations.domain.services.time_tracking_summary import month_totals
from src.modules.operations.domain.services.time_tracking_summary import today_figures
from src.modules.operations.domain.value_objects.time_tracking import TimeTrackingDay
from src.modules.operations.domain.value_objects.time_tracking import TimeTrackingMonth
from src.modules.operations.domain.value_objects.time_tracking import TimeTrackingReadRights
from src.modules.operations.domain.value_objects.time_tracking import TimeTrackingYearSummary


class TimeTrackingMapper:
    @staticmethod
    def rights_to_result(rights: TimeTrackingReadRights) -> TimeTrackingReadRightsResult:
        return TimeTrackingReadRightsResult(days=rights.days, month=rights.month, year=rights.year)

    @staticmethod
    def account_to_result(
        settings: AdminTimeTrackingSettings,
        credentials: UserTimeTrackingCredentials | None,
        *,
        employee_name: str | None = None,
        rights: TimeTrackingReadRights | None = None,
    ) -> TimeTrackingAccountResult:
        reason = credentials_invalid_reason(credentials, current_key_id=settings.credential_key_id)
        return TimeTrackingAccountResult(
            time_tracking_user=credentials.time_tracking_user if credentials else None,
            time_tracking_password_configured=bool(
                credentials and credentials.time_tracking_sealed_credentials
            ),
            time_tracking_credentials_valid=reason is None,
            time_tracking_credentials_invalid_reason=reason.value if reason else None,
            time_tracking_consent_version=TIME_TRACKING_CONSENT_VERSION,
            time_tracking_consent_current=bool(
                credentials
                and credentials.time_tracking_consent_version == TIME_TRACKING_CONSENT_VERSION
            ),
            time_tracking_privacy_policy_url=settings.privacy_policy_url,
            time_tracking_provider_label=settings.provider_label,
            time_tracking_employee_name=employee_name,
            time_tracking_rights=(
                TimeTrackingMapper.rights_to_result(rights) if rights is not None else None
            ),
        )

    @staticmethod
    def day_to_result(day: TimeTrackingDay, *, today: date, now: datetime) -> TimeTrackingDayResult:
        worked = day_worked_seconds(day, today=today, now=now)
        return TimeTrackingDayResult(
            date=day.day,
            weekday=day.day.isoweekday(),
            shift_name=day.shift_name,
            shift_short_name=day.shift_short_name,
            first_in=day.first_in,
            last_out=day.last_out,
            bookings=[
                TimeTrackingBookingResult(at=b.at, direction=b.direction.value)
                for b in day.bookings
            ],
            worked_seconds=worked,
            target_seconds=day.target_seconds,
            day_balance_seconds=worked - day.target_seconds if worked is not None else None,
            running_balance_seconds=day.running_balance_seconds,
            status=day.status.value,
        )

    @staticmethod
    def month_to_result(
        *,
        first_day: date,
        last_day: date,
        month: TimeTrackingMonth | None,
        rights: TimeTrackingReadRights,
        employee_name: str,
        today: date,
        now: datetime,
    ) -> TimeTrackingMonthResult:
        """`month` is None when the account may not read the month; the
        view then shows nothing but the rights."""
        totals: TimeTrackingTotalsResult | None = None
        if month is not None:
            figures = today_figures(month, today=today, now=now)
            sums = month_totals(month, today=today, now=now)
            totals = TimeTrackingTotalsResult(
                today=(
                    TimeTrackingTodayResult(
                        date=figures.day,
                        worked_seconds=figures.worked_seconds,
                        target_seconds=figures.target_seconds,
                        day_balance_seconds=figures.day_balance_seconds,
                        running_balance_seconds=figures.running_balance_seconds,
                        clocked_in=figures.clocked_in,
                        first_in=figures.first_in,
                        target_reached_at=figures.target_reached_at,
                    )
                    if figures is not None
                    else None
                ),
                worked_seconds=sums.worked_seconds,
                target_seconds=sums.target_seconds,
                balance_seconds=sums.balance_seconds,
            )
        return TimeTrackingMonthResult(
            month=f"{first_day.year:04d}-{first_day.month:02d}",
            first_day=first_day,
            last_day=last_day,
            employee_name=employee_name,
            days=(
                [TimeTrackingMapper.day_to_result(d, today=today, now=now) for d in month.days]
                if month is not None
                else []
            ),
            accounts=(
                [
                    TimeTrackingAccountValueResult(
                        account_id=a.account_id,
                        name=a.name,
                        short_name=a.short_name,
                        format=a.format.value,
                        pre=a.pre,
                        sum=a.sum,
                        post=a.post,
                    )
                    for a in month.accounts
                ]
                if month is not None
                else []
            ),
            totals=totals,
            rights=TimeTrackingMapper.rights_to_result(rights),
            fetched_at=now,
        )

    @staticmethod
    def year_to_result(
        *,
        year: int,
        summary: TimeTrackingYearSummary | None,
        rights: TimeTrackingReadRights,
        employee_name: str,
        now: datetime,
    ) -> TimeTrackingYearResult:
        return TimeTrackingYearResult(
            year=year,
            employee_name=employee_name,
            months=(
                [
                    TimeTrackingYearMonthResult(
                        month=m.month,
                        worked_seconds=m.worked_seconds,
                        target_seconds=m.target_seconds,
                        balance_seconds=m.balance_seconds,
                        end_balance_seconds=m.end_balance_seconds,
                    )
                    for m in summary.months
                ]
                if summary is not None
                else []
            ),
            end_balance_seconds=summary.end_balance_seconds if summary is not None else None,
            rights=TimeTrackingMapper.rights_to_result(rights),
            fetched_at=now,
        )
