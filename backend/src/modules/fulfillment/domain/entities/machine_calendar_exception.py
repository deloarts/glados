"""
Per machine, per date, override of the resolved weekly template, holidays,
maintenance windows, extra shifts. Always applies on top,
regardless of whether the machine is using its own MachineWorkingHours
row or AdminProductionSettings.default_weekly_hours underneath. The day's
working time is one interval of available_minutes from start_minute, a
local time like every calendar hour.
"""

from dataclasses import dataclass
from datetime import date
from datetime import datetime

from src.modules.fulfillment.domain.value_objects.work_interval import DEFAULT_DAY_START_MINUTE
from src.modules.fulfillment.domain.value_objects.work_interval import WorkInterval
from src.modules.platform.domain.entities.user import User
from src.shared_kernel.domain.entities.base import Entity


@dataclass
class MachineCalendarException(Entity):
    # ── Server-managed ────────────────────────────────────────────────
    created: datetime
    changed: datetime | None
    changes: list[str]

    # ── Core fields ───────────────────────────────────────────────────
    exception_date: date
    available_minutes: int  # overrides the resolved weekly template for this date; 0 = closed
    note: str | None

    # ── Relations (FK ids only) ───────────────────────────────────────
    creator_id: int
    machine_id: int  # → ProductionMachine

    # Minutes after local midnight the available minutes start at.
    start_minute: int = DEFAULT_DAY_START_MINUTE

    # ── Denormalized (read-only, populated by repository mapper) ──────
    changed_by_id: int | None = None
    changed_by: User | None = None

    @property
    def hours(self) -> tuple[WorkInterval, ...]:
        """The day's working time, nothing when the machine is closed."""
        if self.available_minutes <= 0:
            return ()
        return (WorkInterval(self.start_minute, self.available_minutes),)
