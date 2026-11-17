"""
A downtime window on a production machine: reported when the machine
goes down, closed once it comes back up. `ended_at` stays None while the
machine is still down, at most one such open row exists per machine (see
the partial unique index on its model). Overlapping closed windows on the
same machine are rejected by AddMachineDowntime/UpdateMachineDowntime,
not the database.
"""

from dataclasses import dataclass
from datetime import datetime

from src.modules.fulfillment.domain.value_objects.machine_downtime_reason import (
    MachineDowntimeReason,
)
from src.shared_kernel.domain.entities.base import Entity


@dataclass
class MachineDowntime(Entity):
    # ── Server-managed ────────────────────────────────────────────────
    created: datetime
    changed: datetime | None
    changes: list[str]

    # ── Core fields ───────────────────────────────────────────────────
    machine_id: int  # → ProductionMachine
    started_at: datetime
    ended_at: datetime | None  # None while the machine is still down
    reason: MachineDowntimeReason
    note: str | None

    # ── Audit ─────────────────────────────────────────────────────────
    reported_by_id: int  # → User, who reported the machine going down
    ended_by_id: int | None  # → User, who ended it; None while open

    # ── Denormalized (read-only, populated by repository mapper) ──────
    machine_internal_name: str = ""
    reported_by_full_name: str = ""
    ended_by_full_name: str | None = None
    changed_by_id: int | None = None
    changed_by_full_name: str | None = None
