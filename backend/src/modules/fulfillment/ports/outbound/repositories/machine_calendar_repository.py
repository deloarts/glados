"""
Repository interface for the machine calendar aggregate:
MachineWorkingHours (per-machine weekly template override, at most one
per machine), MachineCalendarException (per machine, per date) and
TenantHoliday (plant-wide closed days), whose own port Platform owns
(tenant_holiday_repository.py). Bundled in one protocol, mirroring how
IProductionLotRepository bundles ProductionLot + LotStep + LotPosition.
"""

from datetime import date
from typing import Protocol
from typing import runtime_checkable

from src.modules.fulfillment.domain.entities.machine_calendar_exception import (
    MachineCalendarException,
)
from src.modules.fulfillment.domain.entities.machine_working_hours import MachineWorkingHours
from src.modules.platform.api import ITenantHolidayRepository


@runtime_checkable
class IMachineCalendarRepository(ITenantHolidayRepository, Protocol):
    # ── Working hours (0..1 per machine) ────────────────────────────────
    async def get_working_hours_by_machine_id(
        self, machine_id: int
    ) -> MachineWorkingHours | None: ...
    async def get_working_hours_by_machine_ids(
        self, machine_ids: list[int]
    ) -> list[MachineWorkingHours]:
        """Batch counterpart to get_working_hours_by_machine_id, mirroring
        get_exceptions_by_machine_ids below: one IN-query for
        every id in `machine_ids` instead of one query per machine, for
        callers (scheduler board/auto-plan/pool recompute) that build a
        calendar for many machines in one pass. Only machines with an
        actual override row are returned (0..1 per machine, same as the
        singular); a caller must `.get(machine_id)` and fall back to the
        admin default exactly as the singular's `None` already means."""
        ...

    async def save_working_hours(self, item: MachineWorkingHours) -> MachineWorkingHours: ...
    async def delete_working_hours(self, item: MachineWorkingHours) -> None: ...

    # ── Calendar exceptions (0..n per machine) ──────────────────────────
    async def get_exceptions_by_machine_id(
        self, machine_id: int
    ) -> list[MachineCalendarException]: ...
    async def get_exceptions_by_machine_ids(
        self, machine_ids: list[int]
    ) -> list[MachineCalendarException]: ...
    async def get_exception_by_id(self, id: int) -> MachineCalendarException | None: ...
    async def get_exception_by_machine_and_date(
        self, machine_id: int, exception_date: date
    ) -> MachineCalendarException | None: ...
    async def save_exception(self, item: MachineCalendarException) -> MachineCalendarException: ...
    async def delete_exception(self, item: MachineCalendarException) -> None: ...
