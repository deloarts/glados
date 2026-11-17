"""
Repository interface for the tenant holidays: public holidays and plant
shutdowns that close every machine. Platform owns them; the machine
calendar repository of Planning & fulfillment extends this port, since one
calendar build reads the holidays with the machines' own hours.
"""

from typing import Protocol
from typing import runtime_checkable

from src.modules.platform.domain.entities.tenant_holiday import TenantHoliday


@runtime_checkable
class ITenantHolidayRepository(Protocol):
    # ── Tenant holidays (plant-wide) ────────────────────────────────────
    async def get_holidays(self) -> list[TenantHoliday]:
        """Every tenant holiday, by start date. The table holds a few rows
        a year, so every calendar build reads all of them."""
        ...

    async def get_holiday_by_id(self, id: int) -> TenantHoliday | None: ...
    async def save_holiday(self, item: TenantHoliday) -> TenantHoliday: ...
    async def delete_holiday(self, item: TenantHoliday) -> None: ...
