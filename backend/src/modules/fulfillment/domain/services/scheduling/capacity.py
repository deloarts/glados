"""Booked and available minutes per day, for the schedule board's capacity row."""

from datetime import date

from src.modules.fulfillment.domain.services.scheduling.machine_calendar import MachineCalendar
from src.modules.fulfillment.domain.services.scheduling.walk_context import ScheduledOrder
from src.shared_kernel.domain.services.clock import as_utc


def compute_daily_capacity(
    calendar: MachineCalendar, scheduled: list[ScheduledOrder], dates: list[date]
) -> dict[date, tuple[int, int]]:
    """Booked and available minutes per day for one machine. A day counts
    the working windows that start on it, a night shift included, and the
    booked minutes are the orders' overlap with those windows."""
    result: dict[date, tuple[int, int]] = {}
    for d in dates:
        windows = calendar.windows_on(d)
        available = calendar.minutes_available_on(d)
        booked = 0.0
        for order in scheduled:
            if order.planned_start is None or order.planned_end is None:
                continue
            order_start, order_end = as_utc(order.planned_start), as_utc(order.planned_end)
            for window_start, window_end in windows:
                overlap_start = max(order_start, window_start)
                overlap_end = min(order_end, window_end)
                if overlap_end > overlap_start:
                    booked += (overlap_end - overlap_start).total_seconds() / 60
        result[d] = (round(booked), available)
    return result
