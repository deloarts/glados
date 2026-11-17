"""
Rules the infoscreen feed applies to the data it gathers: a machine's state
on the board, which order is current and which come next, whether the global
banner shows right now, and the next tenant holiday. No I/O.
"""

from collections.abc import Iterable
from collections.abc import Sequence
from datetime import date
from datetime import datetime
from datetime import timedelta
from typing import Literal

from src.modules.fulfillment.domain.entities.production_order import ProductionOrder
from src.modules.fulfillment.domain.policies.scheduling import MachineCalendar
from src.modules.fulfillment.domain.value_objects.production_status import ProductionOrderStatus
from src.modules.platform.domain.entities.admin_settings.banner import AdminBannerSettings
from src.modules.platform.domain.entities.tenant_holiday import TenantHoliday

MachineState = Literal["running", "idle", "down", "closed"]

_RUNNING = ProductionOrderStatus.IN_PROGRESS.value
_PAUSED = ProductionOrderStatus.PAUSED.value


def is_working_at(calendar: MachineCalendar, moment: datetime) -> bool:
    """Whether `moment` falls inside one of the machine's working windows. A
    window of the previous local day can still run past midnight."""
    local_day = moment.astimezone(calendar.zone).date()
    for day in (local_day - timedelta(days=1), local_day):
        for start, end in calendar.windows_on(day):
            if start <= moment < end:
                return True
    return False


def machine_state(*, down: bool, running: bool, working_now: bool) -> MachineState:
    """Down wins, since a reported downtime is what the shop floor must
    see; a running order wins over the calendar, since the machine runs
    whatever its hours say."""
    if down:
        return "down"
    if running:
        return "running"
    if not working_now:
        return "closed"
    return "idle"


def current_and_next(
    orders: Sequence[ProductionOrder], next_count: int
) -> tuple[ProductionOrder | None, list[ProductionOrder]]:
    """The order on the machine now, a running one before a paused one, and
    the next `next_count` in queue order. `orders` are the machine's live
    orders in queue order."""
    current = next((o for o in orders if o.status == _RUNNING), None)
    if current is None:
        current = next((o for o in orders if o.status == _PAUSED), None)
    upcoming = [o for o in orders if o is not current]
    return current, upcoming[:next_count]


def banner_visible(banner: AdminBannerSettings, now: datetime) -> bool:
    if not banner.enabled or not banner.text.strip():
        return False
    if banner.shows_from is not None and now < banner.shows_from:
        return False
    return not (banner.shows_until is not None and now > banner.shows_until)


def next_holiday(holidays: Iterable[TenantHoliday], today: date) -> TenantHoliday | None:
    """The holiday running today or starting soonest after it."""
    upcoming = [h for h in holidays if h.end_date >= today]
    return min(upcoming, key=lambda h: (h.start_date, h.id)) if upcoming else None


def days_overdue(target: date, today: date) -> int | None:
    """How many days a lot is past its target date, None while it is not."""
    return (today - target).days if target < today else None
