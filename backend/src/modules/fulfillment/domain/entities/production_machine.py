"""
A production machine available for internal manufacturing work: its
capabilities (fabrication methods it supports), operational status, and
whether it is QA-designated.
"""

from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field
from datetime import datetime
from typing import TYPE_CHECKING

from src.shared_kernel.domain.entities.base import Entity

if TYPE_CHECKING:
    from src.modules.catalogue.domain.entities.fabrication_method import FabricationMethod


@dataclass
class ProductionMachine(Entity):
    # ── Server-managed ────────────────────────────────────────────────
    created: datetime
    changed: datetime | None
    changes: list[str]
    archived: bool

    # ── Core fields ───────────────────────────────────────────────────
    internal_name: str
    vendor: str
    model: str

    # FK-id view of the m:n machine_fabrication_method table (variant-level
    # only, a machine is "a 3-axis mill", never just "a mill").
    fabrication_method_ids: list[int]
    max_part_dimension: str | None
    note: str | None

    # ── Audit ─────────────────────────────────────────────────────────
    creator_id: int
    creator_full_name: str = ""
    changed_by_id: int | None = None
    changed_by_full_name: str | None = None

    # Dedicated in-house measuring/QA machine (e.g. a CMM). Selectable only
    # for inspection-role positions and never for fabrication work, see
    # production_order_rules.assert_capability_match.
    is_qa_machine: bool = False

    # Position in the hand-kept order the machine lists, the schedule board
    # and the pickers show the machines in, moved one place at a time from
    # the resources section (shared_kernel list_order).
    sort_order: int = 0

    # ── Denormalized (read-only, populated by repository mapper) ──────
    fabrication_methods: list[FabricationMethod] = field(default_factory=list)
