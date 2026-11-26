"""
Fabrication/manufacturing method configuration: machine requirements,
outsourcing flag, default supplier, and archival.
"""

from dataclasses import dataclass
from datetime import datetime

from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.value_objects.localized_text import LocalizedText
from src.shared_kernel.domain.entities.base import Entity


@dataclass
class FabricationMethod(Entity):
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

    # Whether a step with this method needs a machine at all. A manual-labour
    # step (False, such as gluing) is never assigned a machine or pool and is
    # scheduled against the default calendar.
    requires_machine: bool = True

    # Whether this method is typically outsourced. Assigning a step using it
    # to an internal machine or pool is still allowed; the frontend only
    # flags the unusual choice and never blocks it.
    required_external: bool = False

    # Preferred supplier for external work, a UI hint only; the supplier used
    # is always the one on the order the position is assigned to.
    default_supplier_id: int | None = None

    # Typical calendar days at an external supplier, summed over an EXTERNAL
    # or MIXED position's steps when its order line has no supplier lead time
    # (scheduling.resolve_position_lead_days). None falls back to
    # AdminProductionSettings.default_external_lead_days.
    lead_time_days: int | None = None

    # Clock minutes the pieces wait after a step of this method before the
    # next step may start, such as curing; it runs overnight and over
    # weekends. None waits nothing.
    wait_after_minutes: int | None = None

    # The method preselected for assemblies, read by the SolidWorks add-in
    # when it builds the process of an assembly. At most one method carries
    # it: setting it on one method clears it on the previous holder, and an
    # archived method never carries it, so archiving clears it too.
    default_for_assemblies: bool = False

    # Hides the method from pickers for new steps and processes; steps already
    # using it keep working. Only Archive/RestoreFabricationMethod set it.
    archived: bool = False

    # Position in the hand-kept order pickers offer the methods in, moved one
    # place at a time from the resources section (shared_kernel list_order).
    sort_order: int = 0
