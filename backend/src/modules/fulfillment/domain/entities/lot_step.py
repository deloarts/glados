"""
A single manufacturing step within a ProductionLot's routing, belonging to
exactly one LotPosition. Lot creation snapshots one step per MadeItemProcess,
but a DRAFT lot may add ad-hoc steps or remove any step (see lot_rules.py).
"""

from dataclasses import dataclass
from dataclasses import field
from datetime import datetime

from src.modules.catalogue.domain.value_objects.step_role import StepRole
from src.modules.platform.domain.value_objects.localized_text import LocalizedText
from src.shared_kernel.domain.entities.base import Entity


@dataclass
class LotStep(Entity):
    # ── Server-managed ────────────────────────────────────────────────
    created: datetime

    # ── Core fields ───────────────────────────────────────────────────
    note: str | None
    estimated_setup_minutes: int | None
    estimated_minutes_per_piece: float | None
    sequence: int  # 1-based order within the lot (lot-wide, not per-position)

    # ── Relations (FK ids only) ───────────────────────────────────────
    creator_id: int
    fabrication_method_id: int | None  # None only when role == "inspection"
    lot_id: int  # → ProductionLot
    position_id: int  # → LotPosition (always set)
    source_process_id: (
        int | None
    )  # → MadeItemProcess; None = ad-hoc or catalogue process later deleted

    # ── Step role ────────────────────────────────────────────────────
    # StepRole: FABRICATION (default, tied to fabrication_method_id) |
    # INSPECTION (a QA checkpoint, tied to inspection_method_id instead).
    # See lot_rules.assert_valid_step_role for the invariants.
    role: StepRole = StepRole.FABRICATION
    # → InspectionMethod; None only when role == "fabrication".
    inspection_method_id: int | None = None

    # ── Denormalized (read-only, populated by repository mapper) ──────
    fabrication_method_name: LocalizedText = field(default_factory=LocalizedText)
    # False when the method is manual labour with no machine behind it, such
    # as gluing (see production_order_rules.position_is_manual). The mapper
    # forces False for every inspection step.
    fabrication_method_requires_machine: bool = True
    # True when the method is usually outsourced; assigning its position to an
    # internal machine or pool is allowed but flagged.
    fabrication_method_required_external: bool = False
    # Preferred supplier for external work, a UI pre-fill hint only.
    fabrication_method_default_supplier_id: int | None = None
    # Used by scheduling.resolve_position_lead_days; None for an
    # inspection step or a method without a lead time.
    fabrication_method_lead_time_days: int | None = None
    # Denormalized from InspectionMethod, only set when role == "inspection".
    inspection_method_name: LocalizedText | None = None
    # Only set for inspection steps; drives the evidence-file gate in
    # record_production_order_completion.py.
    inspection_method_requires_evidence: bool | None = None
    # The wait of the step's method, its fabrication method's or, for an
    # inspection step, its inspection method's: clock minutes the pieces
    # wait after the step before the next one may start. None waits nothing.
    method_wait_after_minutes: int | None = None

    # ── Scheduling ───────────────────────────────────────────────────────
    # Per-piece estimate apportioned from the project's production time
    # budget (time_budget_service.py). The scheduler uses it only while
    # estimated_minutes_per_piece is None; a recompute writes it.
    time_budget_per_piece: float | None = None
