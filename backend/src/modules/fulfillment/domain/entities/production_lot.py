"""A ProductionLot: "produce Q pieces of made item M for project P".

The made item and the project are immutable; a lot is one physical run and
never mixes projects. It owns LotSteps, a snapshot of the item's routing at
creation, grouped into LotPositions that are each executed by one party, a
supplier through an OrderItem or in house through ProductionOrders.
"""

from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field
from datetime import date
from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from src.modules.fulfillment.domain.value_objects.lot_origin_disposition import LotOriginDisposition
from src.modules.fulfillment.domain.value_objects.lot_status import LotStatus
from src.modules.fulfillment.domain.value_objects.production_status import UrgencyClass
from src.modules.fulfillment.domain.value_objects.source_approval_status import SourceApprovalStatus
from src.modules.fulfillment.domain.value_objects.source_item_demand_status import (
    SourceItemDemandStatus,
)
from src.shared_kernel.domain.entities.base import Entity

if TYPE_CHECKING:
    from src.modules.fulfillment.domain.entities.lot_position import LotPosition
    from src.modules.fulfillment.domain.entities.lot_step import LotStep
    from src.modules.platform.domain.entities.user import User


@dataclass
class FollowUpLotSummary:
    """A lot spawned from this one by a disposition, as a read-model row."""

    id: int
    lot_number: str
    disposition: LotOriginDisposition
    quantity: float


@dataclass
class ProductionLot(Entity):
    # ── Server-managed ────────────────────────────────────────────────
    created: datetime
    changed: datetime | None
    changes: list[str]

    # ── Core fields ───────────────────────────────────────────────────
    lot_number: str  # generated via AdminMadeItemSettings.lot_number_format
    quantity: float
    # LotStatus: DRAFT | PARTIALLY_PLANNED | PLANNED | IN_PROGRESS | ON_HOLD | COMPLETED |
    # CANCELED | SCRAPPED
    status: LotStatus
    priority: UrgencyClass
    note: str | None

    # ── Relations (FK ids only) ───────────────────────────────────────
    creator_id: int
    made_item_id: int  # → MadeItem; required, immutable for the lifetime of the lot
    project_id: int  # → Project; required, immutable for the lifetime of the lot
    input_demand_id: int | None  # → SourceItemDemandItem, once demanded/ordered

    # ── Material source: at most one set. Seeded from the made item and
    # switchable per lot, including to a made item for rework. ───────────
    source_bought_item_id: int | None = None
    source_item_id: int | None = None
    source_made_item_id: int | None = None  # rework: draws input from this MadeItem

    # The lot an inspection disposition spawned this one from, and why.
    # Both are set or both None. Unrelated to the material source.
    origin_lot_id: int | None = None  # → ProductionLot
    origin_disposition: LotOriginDisposition | None = None

    # An explicit due date that wins over the target derived from demand.
    required_delivery_date: date | None = None

    # Set while the lot is COMPLETED, by the lifecycle reconciler.
    completed_at: datetime | None = None

    # Pieces scrapped in production, at inspection or lost at receipt.
    # `quantity` shrinks by the same amount, and a force-complete closes it
    # at the produced quantity, which leaves this count as it is.
    quantity_scrapped: float = 0.0

    # ── Lifecycle intents ─────────────────────────────────────────────
    # `held_at` is set while the lot is on hold, `canceled_at` once it is
    # canceled and `force_completed_at` once it was force-completed; each is
    # None otherwise. They are the intents the lot's derived status reads
    # (src/modules/fulfillment/domain/services/lifecycle/lot.py).
    held_at: datetime | None = None
    canceled_at: datetime | None = None
    # Moves on every user edit and irreversible action, never on a derived
    # status or date (domain/services/edit_version.py).
    edit_version: int = 0
    force_completed_at: datetime | None = None

    # ── Denormalized (read-only, populated by repository mapper) ──────
    creator: User | None = None
    changed_by_id: int | None = None
    changed_by: User | None = None
    made_item_part_number: str = ""
    made_item_article_name: str = ""
    made_item_revision: str = ""
    made_item_material: str = ""
    # public_id of the made item this lot produces, for print templates
    # that QR-code the item rather than the lot itself.
    made_item_public_id: UUID | None = None
    source_label: str = ""
    source_sublabel: str = ""
    # Material of a source-item source, compared with made_item_material;
    # "" for other sources.
    source_material: str = ""
    # The input demand's status, None without an input demand.
    demand_status: SourceItemDemandStatus | None = None
    # The order the raw material comes in on, through the input demand's
    # allocations. With several orders the latest-dated one wins.
    source_order_id: int | None = None
    source_order_number: str | None = None
    source_expected_delivery_date: date | None = None  # projected (target → date)
    source_delivery_date: datetime | None = None  # confirmed/arrived (event → timestamp)
    project_number: str = ""
    project_customer: str = ""
    product_id: int | None = None
    product_number: str | None = None
    origin_lot_number: str = ""  # denormalized from origin_lot_id, "" when None
    follow_up_lots: list[FollowUpLotSummary] = field(default_factory=list)
    positions: list[LotPosition] = field(default_factory=list)  # ordered by sequence
    steps: list[LotStep] = field(default_factory=list)  # flat, ordered by sequence

    # ── Source item approval. At most one decision, approved or rejected,
    # is recorded at a time. ──────────────────────────────────────────────
    source_approval_status: SourceApprovalStatus = SourceApprovalStatus.NOT_REQUIRED
    source_approved_by_id: int | None = None  # → User
    source_approved_date: datetime | None = None
    source_rejected_by_id: int | None = None  # → User
    source_rejected_date: datetime | None = None
    source_rejection_reason: str | None = None

    @property
    def quantity_completed(self) -> float:
        """The last position's quantity_completed, or 0.0 without positions."""
        if not self.positions:
            return 0.0
        return max(self.positions, key=lambda p: p.sequence).quantity_completed

    @property
    def is_alteration(self) -> bool:
        """True when this lot reworks an existing made item."""
        return self.source_made_item_id is not None
