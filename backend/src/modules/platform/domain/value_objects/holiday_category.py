"""
What closes the plant on a tenant holiday: a public holiday or a plant
shutdown. Both close every machine for the day; the category only tells them
apart in the calendar.
"""

from enum import unique

from src.shared_kernel.domain.value_objects.value_enum import StrValueEnum


@unique
class HolidayCategory(StrValueEnum):
    PUBLIC_HOLIDAY = "public_holiday"
    PLANT_SHUTDOWN = "plant_shutdown"
