"""
Per-machine override of AdminProductionSettings.default_weekly_hours.
Optional, not a row every machine must have, the scheduler resolves a
machine's calendar as "this machine's own row if one exists, else the
global default" (scheduling.resolve_weekly_minutes), so only
machines that genuinely run different hours (e.g. a night-shift-only
mill) need one at all.
"""

from dataclasses import dataclass
from datetime import datetime

from src.modules.fulfillment.domain.value_objects.work_interval import DayHours
from src.modules.platform.domain.entities.user import User
from src.shared_kernel.domain.entities.base import Entity


@dataclass
class MachineWorkingHours(Entity):
    # ── Server-managed ────────────────────────────────────────────────
    created: datetime
    changed: datetime | None
    changes: list[str]

    # ── Core fields ───────────────────────────────────────────────────
    # weekday (0=Monday..6=Sunday, matches date.weekday()) -> the working
    # intervals that day, local to the tenant (value_objects/work_interval.py);
    # none means the machine doesn't run that day.
    weekly_hours: dict[int, DayHours]

    # ── Relations (FK ids only) ───────────────────────────────────────
    creator_id: int
    machine_id: int  # → ProductionMachine; one override template per machine

    # ── Denormalized (read-only, populated by repository mapper) ──────
    changed_by_id: int | None = None
    changed_by: User | None = None
