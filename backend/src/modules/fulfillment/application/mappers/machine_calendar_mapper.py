"""Converts between MachineWorkingHours/MachineCalendarException domain entities and DTOs,
and between a week of working intervals and its DTO form."""

from collections.abc import Mapping
from collections.abc import Sequence

from src.modules.fulfillment.application.dto.machine_calendar_dto import (
    MachineCalendarExceptionResult,
)
from src.modules.fulfillment.application.dto.machine_calendar_dto import MachineWorkingHoursResult
from src.modules.fulfillment.application.dto.machine_calendar_dto import WorkIntervalDto
from src.modules.fulfillment.domain.entities.machine_calendar_exception import (
    MachineCalendarException,
)
from src.modules.fulfillment.domain.entities.machine_working_hours import MachineWorkingHours
from src.modules.fulfillment.domain.value_objects.work_interval import DayHours
from src.modules.fulfillment.domain.value_objects.work_interval import WorkInterval
from src.modules.fulfillment.domain.value_objects.work_interval import clock_minute
from src.modules.fulfillment.domain.value_objects.work_interval import day_intervals
from src.modules.platform.application.mappers.user_mapper import UserMapper


def weekly_hours_to_dto(weekly: Mapping[int, DayHours]) -> dict[int, list[WorkIntervalDto]]:
    return {
        day: [WorkIntervalDto(start=i.start_clock, minutes=i.minutes) for i in day_intervals(hours)]
        for day, hours in weekly.items()
    }


def weekly_hours_from_dto(
    weekly: Mapping[int, Sequence[WorkIntervalDto]],
) -> dict[int, DayHours]:
    return {
        day: tuple(WorkInterval(clock_minute(i.start), i.minutes) for i in intervals)
        for day, intervals in weekly.items()
    }


class MachineWorkingHoursMapper:
    @staticmethod
    def to_result(entity: MachineWorkingHours) -> MachineWorkingHoursResult:
        return MachineWorkingHoursResult(
            id=entity.id,
            public_id=entity.public_id,
            created=entity.created,
            changed=entity.changed,
            machine_id=entity.machine_id,
            weekly_hours=weekly_hours_to_dto(entity.weekly_hours),
            creator_id=entity.creator_id,
            changed_by_id=entity.changed_by_id,
            changed_by=UserMapper.to_public_result(entity.changed_by)
            if entity.changed_by
            else None,
        )


class MachineCalendarExceptionMapper:
    @staticmethod
    def to_result(entity: MachineCalendarException) -> MachineCalendarExceptionResult:
        return MachineCalendarExceptionResult(
            id=entity.id,
            public_id=entity.public_id,
            created=entity.created,
            changed=entity.changed,
            machine_id=entity.machine_id,
            exception_date=entity.exception_date,
            available_minutes=entity.available_minutes,
            start=WorkInterval(entity.start_minute, entity.available_minutes).start_clock,
            note=entity.note,
            creator_id=entity.creator_id,
            changed_by_id=entity.changed_by_id,
            changed_by=UserMapper.to_public_result(entity.changed_by)
            if entity.changed_by
            else None,
        )
