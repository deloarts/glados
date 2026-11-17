"""
The JSON form of a calendar's working hours: a weekday (as a string key) to
a list of {"start_minute", "minutes"} intervals. A day stored as a plain
minute count, the form before intervals, still reads as one interval from
the default day start.
"""

from collections.abc import Mapping
from typing import Any

from src.modules.fulfillment.domain.value_objects.work_interval import DayHours
from src.modules.fulfillment.domain.value_objects.work_interval import WorkInterval
from src.modules.fulfillment.domain.value_objects.work_interval import day_intervals


def hours_to_json(hours: DayHours) -> list[dict[str, int]]:
    return [{"start_minute": i.start_minute, "minutes": i.minutes} for i in day_intervals(hours)]


def hours_from_json(value: Any) -> tuple[WorkInterval, ...]:
    if isinstance(value, int):
        return day_intervals(value)
    return day_intervals(
        [WorkInterval(int(i["start_minute"]), int(i["minutes"])) for i in value or []]
    )


def weekly_to_json(weekly: Mapping[int, DayHours]) -> dict[str, list[dict[str, int]]]:
    return {str(day): hours_to_json(hours) for day, hours in weekly.items()}


def weekly_from_json(value: Mapping[str, Any] | None) -> dict[int, DayHours]:
    return {int(day): hours_from_json(hours) for day, hours in (value or {}).items()}
