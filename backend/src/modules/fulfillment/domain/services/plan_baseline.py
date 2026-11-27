"""
The rules of the nightly baseline: how far the committed horizon reaches,
which orders it records, and when a lot was planned to finish.

The baseline records the dates the active scheduler persisted. It never
dates anything itself, so it shows the plan as the floor saw it that
morning, and the dates of later days can be compared against it.
"""

from collections.abc import Iterable
from collections.abc import Mapping
from datetime import UTC
from datetime import date
from datetime import datetime
from datetime import time
from datetime import timedelta

from src.modules.fulfillment.domain.entities.production_order import ProductionOrder
from src.modules.fulfillment.domain.entities.production_plan import ProductionPlanEntry
from src.modules.fulfillment.domain.policies.wait_after import latest_ready_moment
from src.modules.fulfillment.domain.services.scheduling.machine_calendar import MachineCalendar
from src.modules.fulfillment.domain.value_objects.production_status import (
    TERMINAL_PRODUCTION_ORDER_STATUSES,
)
from src.modules.fulfillment.domain.value_objects.production_status import ProductionOrderStatus
from src.shared_kernel.domain.services.clock import as_utc

# How far ahead the horizon search looks for working days, a defensive bound
# for a calendar that has almost none.
_SEARCH_DAYS = 366


def commit_horizon_end(today: date, working_days: int, calendar: MachineCalendar) -> datetime:
    """The end of the committed horizon: the start of the local day after the
    `working_days`-th working day from today, today included when it is a
    working day. A working day is one the calendar gives working time.
    Without enough working days in a year, the horizon spans `working_days`
    calendar days instead."""
    found = 0
    for offset in range(_SEARCH_DAYS):
        day = today + timedelta(days=offset)
        if calendar.minutes_available_on(day) > 0:
            found += 1
            if found >= working_days:
                return _day_start(day + timedelta(days=1), calendar)
    return _day_start(today + timedelta(days=working_days), calendar)


def baseline_entries(
    orders: Iterable[ProductionOrder], horizon_end: datetime
) -> list[ProductionPlanEntry]:
    """One entry per open order that starts before the horizon ends, in queue
    order per machine. An order the scheduler left undated has no window to
    record."""
    entries = [
        ProductionPlanEntry(
            id=0,
            production_order_id=order.id,
            lot_position_id=order.lot_position_id,
            lot_id=order.lot_id,
            position_sequence=order.lot_position_sequence,
            production_order_number=order.production_order_number,
            machine_id=order.machine_id,
            machine_pool_id=order.machine_pool_id,
            queue_sequence=order.queue_sequence,
            planned_start=order.planned_start,
            planned_end=order.planned_end,
            duration_minutes=order.estimated_duration_minutes,
        )
        for order in orders
        if order.status not in TERMINAL_PRODUCTION_ORDER_STATUSES
        and order.planned_start is not None
        and as_utc(order.planned_start) < horizon_end
    ]
    return sorted(
        entries,
        key=lambda e: (e.machine_id or 0, e.queue_sequence, e.production_order_id or 0),
    )


def lot_planned_finishes(
    orders: Iterable[ProductionOrder],
    lot_of_position: Mapping[int, int],
    wait_by_position: Mapping[int, int],
) -> dict[int, datetime]:
    """When each lot's last pieces were planned to be ready: the latest
    planned end of an open order plus the wait after its position, and a
    completed order's actual end plus that wait while the wait still runs.
    A lot whose open orders are all undated has no finish."""
    ends_by_lot: dict[int, list[tuple[datetime | None, int]]] = {}
    for order in orders:
        lot_id = lot_of_position.get(order.lot_position_id)
        if lot_id is None:
            continue
        wait = wait_by_position.get(order.lot_position_id, 0)
        if order.status not in TERMINAL_PRODUCTION_ORDER_STATUSES:
            ends_by_lot.setdefault(lot_id, []).append((order.planned_end, wait))
        elif order.status == ProductionOrderStatus.COMPLETED and wait > 0:
            ends_by_lot.setdefault(lot_id, []).append((order.actual_end, wait))
    return {
        lot_id: moment
        for lot_id, ends in ends_by_lot.items()
        if (moment := latest_ready_moment(ends)) is not None
    }


def _day_start(day: date, calendar: MachineCalendar) -> datetime:
    return datetime.combine(day, time(0, 0), tzinfo=calendar.zone).astimezone(UTC)
