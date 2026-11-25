"""
Quality inspection/QA method: evidence requirements, default durations,
default machine assignment, and archival flag.
"""

from dataclasses import dataclass
from datetime import datetime

from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.value_objects.localized_text import LocalizedText
from src.shared_kernel.domain.entities.base import Entity


@dataclass
class InspectionMethod(Entity):
    # ── Server-managed ────────────────────────────────────────────────
    created: datetime
    changed: datetime
    changes: list[str]

    # ── Core fields ───────────────────────────────────────────────────
    name: LocalizedText
    label_color: str
    label_font_color: str
    description: LocalizedText

    # ── Audit ─────────────────────────────────────────────────────────
    creator_id: int
    creator: User | None = None
    changed_by_id: int | None = None
    changed_by: User | None = None

    # Whether a completion against a step with this method needs at least one
    # measurement_report evidence file on the production order first (see
    # record_production_order_completion.py).
    requires_evidence: bool = False

    # Default durations for a step or process created with this method. They
    # live here because inspection time depends on the method, not the
    # project. They are seeded at creation only, so a hand-tuned estimate never
    # reverts when the method is edited; None leaves the step without an
    # estimate, which estimate_time_source reports as "not_applicable".
    default_setup_minutes: int | None = None
    default_minutes_per_piece: float | None = None

    # Clock minutes the pieces wait after a check of this method before the
    # next step may start, such as for a lab result; it runs overnight and
    # over weekends. None waits nothing.
    wait_after_minutes: int | None = None

    # Hides the method from pickers for new steps; steps already using it keep
    # working. It cannot be archived while it is the production settings'
    # default_inspection_method_id, and only Archive/RestoreInspectionMethod
    # set it.
    archived: bool = False

    # Optional QA machine pre-filled onto a step's auto-queued production order
    # at lot creation (create_lot.py); Auto-Plan never invents one. It is not
    # re-validated, so a machine that later becomes unusable only makes the
    # next lot's pre-fill machine-less.
    default_machine_id: int | None = None
    # Not persisted; the repository mapper fills it from default_machine_id.
    default_machine_name: str | None = None

    # Position in the hand-kept order pickers offer the methods in, moved one
    # place at a time from the resources section (shared_kernel list_order).
    sort_order: int = 0
