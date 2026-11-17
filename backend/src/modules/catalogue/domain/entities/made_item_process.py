"""
Ordered process step of a MadeItem's routing: each step is tied to
a fabrication method and carries its own estimated setup + per-piece time.
"""

from dataclasses import dataclass
from dataclasses import field
from datetime import datetime

from src.modules.catalogue.domain.value_objects.step_role import StepRole
from src.modules.platform.domain.value_objects.localized_text import LocalizedText
from src.shared_kernel.domain.entities.base import Entity


@dataclass
class MadeItemProcess(Entity):
    # ── Server-managed ────────────────────────────────────────────────
    created: datetime

    # ── Core fields ───────────────────────────────────────────────────
    note: str | None
    estimated_setup_minutes: int | None
    estimated_minutes_per_piece: float | None

    # ── Relations (FK ids only) ───────────────────────────────────────
    creator_id: int
    fabrication_method_id: int | None  # None only when role == "inspection"
    made_item_id: int
    position: int
    group_index: int

    # ── Step role ────────────────────────────────────────────────────
    # StepRole: FABRICATION (default, tied to fabrication_method_id) |
    # INSPECTION (a QA checkpoint, tied to inspection_method_id instead).
    # See made_item_rules.assert_valid_step_role for the invariants.
    role: StepRole = StepRole.FABRICATION
    # → InspectionMethod; None only when role == "fabrication".
    inspection_method_id: int | None = None

    # ── Denormalized (read-only, populated by repository mapper) ──────
    fabrication_method_name: LocalizedText = field(default_factory=LocalizedText)
    # Denormalized from InspectionMethod, only set when role == "inspection".
    inspection_method_name: LocalizedText | None = None
