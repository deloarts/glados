"""
A project's expressed need for a MadeItem.
Who needs it, how many, for which project, by when.
Status: OPEN | ALLOCATED | ORDERED | FULFILLED | CANCELED
Field-for-field mirror of BoughtItemDemandItem.
"""

from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field
from datetime import date
from datetime import datetime
from typing import TYPE_CHECKING

from src.modules.catalogue.domain.value_objects.made_item_status import MadeItemDemandStatus
from src.modules.workspace.domain.value_objects.project_status import ProjectStatus
from src.shared_kernel.domain.entities.base import Entity

if TYPE_CHECKING:
    from src.modules.catalogue.domain.entities.made_item import MadeItem
    from src.modules.platform.domain.entities.user import User


@dataclass
class MadeItemDemandItem(Entity):
    # ── Server-managed ────────────────────────────────────────────────
    created: datetime
    changed: datetime | None
    changes: list[str]

    # ── Core fields ───────────────────────────────────────────────────
    status: MadeItemDemandStatus  # OPEN | ALLOCATED | ORDERED | FULFILLED | CANCELED
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
    made_item_id: int  # → MadeItem (the catalogue entry)
    project_id: int  # → Project

    # ── Alteration, this demand is a rework of an existing made item,
    # not a fresh build. alteration_of_made_item_id is required when
    # is_alteration is set, and must reference a different MadeItem than
    # made_item_id (see made_item_demand_rules.assert_valid_alteration).
    # When allocated to a lot, the lot's source_made_item_id is set to
    # this id, which is what actually lights up ProductionLot.is_alteration
    # and the lots table's existing alteration tag. ────────────────────
    is_alteration: bool = False
    alteration_of_made_item_id: int | None = None

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
    item_part_number: str = ""
    item_revision: str = ""
    item_article_name: str = ""
    project_number: str = ""
    project_customer: str = ""
    project_description: str = ""
    project_status: ProjectStatus = ProjectStatus.ARCHIVED  # of the owning project
    item: MadeItem | None = field(default=None)
    alteration_of_made_item_part_number: str = ""
    alteration_of_made_item_revision: str = ""
    alteration_of_made_item_article_name: str = ""
