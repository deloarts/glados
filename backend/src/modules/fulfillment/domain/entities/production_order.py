"""Queued internal work against one lot position: machine fabrication,
manual labor or a QA inspection, all through the same machinery. Several
orders may split one position across machines; their quantities sum to
the position's quantity once it is fully queued.

machine_id stays None for manual and inspection work and for a
pool-assigned order until Auto-Plan or Start resolves it.
"""

from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field
from datetime import date
from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from src.modules.fulfillment.domain.value_objects.production_status import ProductionOrderStatus
from src.modules.fulfillment.domain.value_objects.production_status import UrgencyClass
from src.shared_kernel.domain.entities.base import Entity

if TYPE_CHECKING:
    from src.modules.fulfillment.domain.entities.manufacturing_assessment import (
        ManufacturingAssessment,
    )
    from src.modules.fulfillment.domain.entities.production_order_completion import (
        ProductionOrderCompletion,
    )
    from src.modules.fulfillment.domain.entities.production_order_interruption import (
        ProductionOrderInterruption,
    )
    from src.modules.platform.domain.entities.user import User


@dataclass
class ProductionOrder(Entity):
    # ── Server-managed ────────────────────────────────────────────────
    created: datetime
    changed: datetime | None
    changes: list[str]

    # ── Core fields ───────────────────────────────────────────────────
    production_order_number: str
    status: ProductionOrderStatus  # QUEUED | IN_PROGRESS | PAUSED | COMPLETED | CANCELED
    priority: UrgencyClass  # inherited from the lot, overridable
    pinned: bool  # planner-locked; the auto-plan scheduler never moves pinned orders
    queue_sequence: int  # position in the machine's queue
    quantity: float
    quantity_completed: float  # running total, stored (source for LotPosition's aggregate)
    estimated_duration_minutes: int
    note: str | None

    # ── Scheduling (set by the scheduler; None until a plan is computed) ─
    planned_start: datetime | None
    planned_end: datetime | None
    not_before: date | None

    # ── Actuals ──────────────────────────────────────────────────────
    actual_start: datetime | None
    actual_end: datetime | None

    # ── Relations (FK ids only) ─────────────────────────────────────
    creator_id: int
    machine_id: int | None  # → ProductionMachine; None = not yet routed to a machine
    lot_position_id: int  # → LotPosition, NOT unique; a position can be split across several orders

    # → MachinePool. With machine_id unset the order awaits a concrete
    # member; once resolved it keeps the pool for grouping and rollups.
    machine_pool_id: int | None = None

    # Who set the current plan; None means the scheduler did.
    planned_by_id: int | None = None

    # The operator of the latest start or resume.
    started_operator_id: int | None = None

    # planned_end frozen at the first start, the baseline for schedule
    # adherence, since the live planned_end keeps moving.
    planned_end_at_start: datetime | None = None

    # When the order was canceled, None until then: the intent the order's
    # derived status reads (src/modules/fulfillment/domain/services/lifecycle/production_order.py).
    canceled_at: datetime | None = None
    # Moves on every user edit and irreversible action, never on a derived
    # status or date (domain/services/edit_version.py).
    edit_version: int = 0
    # The row version this copy was read at, which the save checks against
    # the row, so a copy older than a committed change is refused; 0 for an
    # order not saved yet.
    version: int = 0

    # ── Denormalized (read-only, populated by repository mapper) ─────
    creator: User | None = None
    changed_by_id: int | None = None
    changed_by: User | None = None
    planned_by: User | None = None
    started_operator: User | None = None
    machine_internal_name: str = ""
    machine_pool_name: str = ""
    lot_id: int = 0
    lot_number: str = ""
    # public_ids of the lot/made item this order belongs to, for print
    # templates that QR-code a different record than the order itself.
    lot_public_id: UUID | None = None
    made_item_public_id: UUID | None = None
    project_id: int | None = None
    project_number: str = ""
    product_id: int | None = None
    product_number: str | None = None
    made_item_part_number: str = ""
    made_item_id: int = 0
    made_item_revision: str = ""
    made_item_article_name: str = ""  # matches MadeItem.article_name; label printing needs it
    made_item_material: str | None = None
    made_item_mass: int | None = None  # grams, matches MadeItem.mass
    made_item_base_size: str | None = None  # matches MadeItem.base_size
    lot_position_sequence: int = 0  # this order's routing step, 1-based
    lot_position_count: int = 0  # total positions/steps on the lot
    completions: list[ProductionOrderCompletion] = field(default_factory=list)
    # Pause and resume cycles, oldest first; read-only here.
    interruptions: list[ProductionOrderInterruption] = field(default_factory=list)
    waiting_on_raw_material: bool = False
    # Computed on read: Start would accept the order on state grounds,
    # ignoring the actor's permissions.
    can_start: bool = False
    # Computed on read for the reading user: the actions the production
    # order intent table allows now (lifecycle/intents.py).
    actions: list[str] = field(default_factory=list)
    assessment: ManufacturingAssessment | None = None

    @property
    def pieces_processed(self) -> float:
        """Pieces the order processed, accepted and rejected alike, from its
        completion rows."""
        return sum((c.quantity for c in self.completions), 0.0)

    @property
    def pieces_accepted(self) -> float:
        """Accepted pieces of the order's completion rows. A reversal books
        the accepted pieces of the batch it takes back negative, so it nets
        out."""
        return sum((c.quantity_accepted for c in self.completions), 0.0)
