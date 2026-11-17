"""
DTOs for the machine calendar aggregate: per-machine working
hours override and calendar exceptions.
"""

from datetime import date
from datetime import datetime

from pydantic import BaseModel
from pydantic import Field

from src.modules.fulfillment.domain.value_objects.work_interval import CLOCK_PATTERN
from src.modules.fulfillment.domain.value_objects.work_interval import DEFAULT_DAY_START_MINUTE
from src.modules.fulfillment.domain.value_objects.work_interval import MINUTES_PER_DAY
from src.modules.platform.application.dto.base import ResultBase
from src.modules.platform.application.dto.user_dto import PublicUserResult

DEFAULT_DAY_START = f"{DEFAULT_DAY_START_MINUTE // 60:02d}:{DEFAULT_DAY_START_MINUTE % 60:02d}"


class WorkIntervalDto(BaseModel):
    """Working time from a local "HH:MM" start for a number of minutes."""

    start: str = Field(..., pattern=CLOCK_PATTERN)
    minutes: int = Field(..., ge=0, le=MINUTES_PER_DAY)


# ══════════════════════════════════════════════════════════════════════
# Commands
# ══════════════════════════════════════════════════════════════════════


class SetMachineWorkingHoursCommand(BaseModel):
    # weekday (0=Monday..6=Sunday) -> working intervals that day, none = off
    weekly_hours: dict[int, list[WorkIntervalDto]]


class CreateMachineCalendarExceptionCommand(BaseModel):
    exception_date: date
    available_minutes: int = Field(..., ge=0, le=MINUTES_PER_DAY)
    start: str = Field(default=DEFAULT_DAY_START, pattern=CLOCK_PATTERN)
    note: str | None = None


class UpdateMachineCalendarExceptionCommand(BaseModel):
    available_minutes: int = Field(..., ge=0, le=MINUTES_PER_DAY)
    start: str = Field(default=DEFAULT_DAY_START, pattern=CLOCK_PATTERN)
    note: str | None = None


# ══════════════════════════════════════════════════════════════════════
# Results
# ══════════════════════════════════════════════════════════════════════


class MachineWorkingHoursResult(ResultBase):
    created: datetime
    changed: datetime | None
    machine_id: int
    weekly_hours: dict[int, list[WorkIntervalDto]]
    creator_id: int
    changed_by_id: int | None
    changed_by: PublicUserResult | None


class MachineCalendarExceptionResult(ResultBase):
    created: datetime
    changed: datetime | None
    machine_id: int
    exception_date: date
    available_minutes: int
    start: str
    note: str | None
    creator_id: int
    changed_by_id: int | None
    changed_by: PublicUserResult | None
