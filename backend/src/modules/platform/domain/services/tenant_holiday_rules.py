"""Rules for the tenant holiday calendar."""

from datetime import date

from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.exceptions import InvalidScheduleCalendarError
from src.modules.platform.domain.services.crud_permission_rules import assert_has_permission
from src.modules.platform.domain.value_objects.permission import Permission

# A shutdown longer than a year is a calendar mistake, not a plan.
MAX_HOLIDAY_DAYS = 366


def validate_holiday(name: str, start_date: date, end_date: date) -> None:
    """A holiday has a name and runs forward for at most MAX_HOLIDAY_DAYS."""
    if not name.strip():
        raise InvalidScheduleCalendarError("A holiday needs a name.")
    if end_date < start_date:
        raise InvalidScheduleCalendarError("A holiday cannot end before it starts.")
    if (end_date - start_date).days + 1 > MAX_HOLIDAY_DAYS:
        raise InvalidScheduleCalendarError(
            f"A holiday cannot run longer than {MAX_HOLIDAY_DAYS} days."
        )


class TenantHolidayRules:
    """Holidays close machine calendars, so they share the machine permissions."""

    @staticmethod
    def assert_can_write(actor: User) -> None:
        assert_has_permission(actor, Permission.WRITE_MACHINES, "change", "holidays")

    @staticmethod
    def assert_can_delete(actor: User) -> None:
        assert_has_permission(actor, Permission.WRITE_MACHINES, "delete", "holidays")
