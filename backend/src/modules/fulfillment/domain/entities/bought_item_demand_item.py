"""
A project's expressed need for a BoughtItem.
Who needs it, how many, for which project, by when.
Status: OPEN | ALLOCATED | ORDERED | FULFILLED | CANCELED
"""

from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field
from datetime import date
from datetime import datetime
from typing import TYPE_CHECKING

from src.modules.catalogue.domain.value_objects.bought_item_status import BoughtItemDemandStatus
from src.modules.workspace.domain.value_objects.project_status import ProjectStatus
from src.shared_kernel.domain.entities.base import Entity

if TYPE_CHECKING:
    from src.modules.catalogue.domain.entities.bought_item import BoughtItem
    from src.modules.platform.domain.entities.user import User


@dataclass
class BoughtItemDemandItem(Entity):
    # ── Server-managed ────────────────────────────────────────────────
    created: datetime
    changed: datetime | None
    changes: list[str]

    # ── Core fields ───────────────────────────────────────────────────
    status: BoughtItemDemandStatus  # OPEN | ALLOCATED | ORDERED | FULFILLED | CANCELED
    quantity: float
    unit: str
    items_per_unit: float

    # ── Additional fields ─────────────────────────────────────────────
    high_priority: bool
    notify_on_delivery: bool
    note: str | None
    desired_delivery_date: date | None

    # ── Relations (FK ids only) ───────────────────────────────────────
    creator_id: int
    item_id: int  # → BoughtItem (the catalogue entry)
    project_id: int  # → Project

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
    item_order_code_1: str = ""
    item_article_name: str = ""
    project_number: str = ""
    project_customer: str = ""
    project_description: str = ""
    project_status: ProjectStatus = ProjectStatus.ARCHIVED  # of the owning project
    item: BoughtItem | None = field(default=None)
