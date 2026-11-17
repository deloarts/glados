"""
Demand for a lot's source item (the "Demand Source Item" flow), one-shot,
always scoped to a single ProductionLot (unlike BoughtItemDemandItem, which
is pooled/reusable across many lots). Fulfilled via the same allocation-pool
architecture as BoughtItemDemandItem (SourceItemDemandAllocation, many
demands can share one order item and vice versa, plus stock-only
fulfillment). status is a real stored field, derived from the demand's
allocations and intents by the lifecycle reconciler
(domain/services/lifecycle/demand.py), not at read time.
"""

from dataclasses import dataclass
from datetime import date
from datetime import datetime

from src.modules.catalogue.domain.entities.bought_item import BoughtItem
from src.modules.catalogue.domain.entities.source_item import SourceItem
from src.modules.fulfillment.domain.value_objects.source_item_demand_status import (
    SourceItemDemandStatus,
)
from src.modules.platform.domain.entities.user import User
from src.modules.workspace.domain.value_objects.project_status import ProjectStatus
from src.shared_kernel.domain.entities.base import Entity


@dataclass
class SourceItemDemandItem(Entity):
    # ── Server-managed ────────────────────────────────────────────────
    created: datetime
    changed: datetime | None
    changes: list[str]

    # ── Core fields ───────────────────────────────────────────────────
    status: SourceItemDemandStatus  # OPEN | ALLOCATED | ORDERED | FULFILLED | CANCELED
    quantity: float
    unit: str
    items_per_unit: float
    high_priority: bool
    notify_on_delivery: bool
    note: str | None
    desired_delivery_date: date | None

    # ── Relations (FK ids only) ───────────────────────────────────────
    creator_id: int
    # Denormalized copy of the lot's material source at creation time,
    # exactly one is set (never both), since a lot whose source is a made
    # item (rework) can't reach this entity at all (create rejects it).
    bought_item_id: int | None
    source_item_id: int | None
    lot_id: int
    project_id: int

    # ── Bucket assignment (display state only, see DemandBucketRules) ──
    bucket_id: int | None = None

    # ── Lifecycle intents ─────────────────────────────────────────────
    # When the demand was canceled and when a user marked it fulfilled by
    # hand, None until then: the intents the demand's derived status reads
    # before its allocations (src/modules/fulfillment/domain/services/lifecycle/demand.py).
    canceled_at: datetime | None = None
    fulfilled_manually_at: datetime | None = None

    # ── Denormalized (read-only, populated by repository mapper) ──────
    creator: User | None = None
    changed_by_id: int | None = None
    changed_by: User | None = None
    bought_item: BoughtItem | None = None
    source_item: SourceItem | None = None
    lot_number: str = ""
    project_number: str = ""
    project_customer: str = ""
    project_description: str = ""
    project_status: ProjectStatus = ProjectStatus.ARCHIVED  # of the owning project
