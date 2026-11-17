"""
A named, archivable grouping of interchangeable ProductionMachine rows.
Auto-Plan's pool-first scheduling can assign an order to a pool before a
concrete machine is chosen, with the machine resolved later.
"""

from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field
from datetime import datetime
from typing import TYPE_CHECKING

from src.shared_kernel.domain.entities.base import Entity

if TYPE_CHECKING:
    from src.modules.fulfillment.domain.entities.production_machine import ProductionMachine


@dataclass
class MachinePool(Entity):
    # ── Server-managed ────────────────────────────────────────────────
    created: datetime
    changed: datetime | None
    changes: list[str]
    archived: bool

    # ── Core fields ───────────────────────────────────────────────────
    name: str

    # FK-id view of the m:n machine_pool_machine table.
    machine_ids: list[int]
    note: str | None

    # ── Audit ─────────────────────────────────────────────────────────
    creator_id: int
    creator_full_name: str = ""
    changed_by_id: int | None = None
    changed_by_full_name: str | None = None

    # Position in the hand-kept order the pool lists and pickers show the
    # pools in, changed by dragging a row in the resources section
    # (shared_kernel list_order).
    sort_order: int = 0

    # ── Denormalized (read-only, populated by repository mapper) ──────
    machines: list[ProductionMachine] = field(default_factory=list)
