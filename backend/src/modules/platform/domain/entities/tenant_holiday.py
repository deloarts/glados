"""
A day or a run of days on which the whole plant does not work: a public
holiday or a plant shutdown. Every machine's calendar is closed on those
days, under the machine's own calendar exceptions, so an exception still
opens a machine on a holiday.
"""

from collections.abc import Iterator
from dataclasses import dataclass
from datetime import date
from datetime import datetime
from datetime import timedelta

from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.value_objects.holiday_category import HolidayCategory
from src.shared_kernel.domain.entities.base import Entity


@dataclass
class TenantHoliday(Entity):
    # ── Server-managed ────────────────────────────────────────────────
    created: datetime
    changed: datetime | None
    changes: list[str]

    # ── Core fields ───────────────────────────────────────────────────
    name: str
    category: HolidayCategory
    start_date: date
    end_date: date  # inclusive; equal to start_date for a single day

    # ── Relations (FK ids only) ───────────────────────────────────────
    creator_id: int

    # ── Denormalized (read-only, populated by repository mapper) ──────
    changed_by_id: int | None = None
    changed_by: User | None = None

    def dates(self) -> Iterator[date]:
        for offset in range((self.end_date - self.start_date).days + 1):
            yield self.start_date + timedelta(days=offset)
