"""
Reads what the display power rules need from outside the terminal: the
tenant timezone, the days of the tenant holidays around today and the
default display schedule.
"""

from datetime import date
from datetime import datetime
from datetime import timedelta

from src.modules.operations.domain.services.display_power_rules import HORIZON_DAYS
from src.modules.operations.domain.value_objects.display_schedule import DisplayCalendar
from src.modules.operations.ports.outbound.repositories.infoscreen_repository import (
    IInfoscreenRepository,
)
from src.modules.platform.api import IPlatformSettingsRepository
from src.modules.platform.api import ITenantHolidayRepository
from src.modules.platform.application.services.tenant_timezone import tenant_zone


class DisplayCalendarReader:
    def __init__(
        self,
        settings_repo: IPlatformSettingsRepository,
        holiday_repo: ITenantHolidayRepository,
        infoscreen_repo: IInfoscreenRepository,
    ) -> None:
        self._settings = settings_repo
        self._holidays = holiday_repo
        self._screens = infoscreen_repo

    async def read(self, now: datetime) -> DisplayCalendar:
        """The tenant zone, every holiday day from yesterday to the end of
        the horizon the rules look at, and the default schedule."""
        zone = await tenant_zone(self._settings)
        today = now.astimezone(zone).date()
        first, last = today - timedelta(days=2), today + timedelta(days=HORIZON_DAYS + 2)
        days: set[date] = set()
        for holiday in await self._holidays.get_holidays():
            if holiday.end_date < first or holiday.start_date > last:
                continue
            days.update(d for d in holiday.dates() if first <= d <= last)
        return DisplayCalendar(
            zone=zone,
            holidays=frozenset(days),
            default=await self._screens.get_display_default(),
        )
