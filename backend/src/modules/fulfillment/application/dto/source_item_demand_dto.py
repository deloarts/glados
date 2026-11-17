"""
DTOs for the SourceItemDemandItem aggregate.
"""

from datetime import date
from datetime import datetime

from pydantic import BaseModel
from pydantic import Field

from src.modules.catalogue.application.dto.bought_item_dto import BoughtItemResult
from src.modules.catalogue.application.dto.source_item_dto import SourceItemResult
from src.modules.platform.application.dto.base import ResultBase
from src.modules.platform.application.dto.user_dto import PublicUserResult

# ══════════════════════════════════════════════════════════════════════
# SourceItemDemandItem
# ══════════════════════════════════════════════════════════════════════


class CreateSourceItemDemandCommand(BaseModel):
    lot_id: int = Field(..., gt=0)
    quantity: float = Field(..., gt=0)
    unit: str = Field(default="pcs", min_length=1)
    items_per_unit: float = Field(default=1.0, gt=0)
    high_priority: bool = False
    notify_on_delivery: bool = False
    note: str | None = None
    desired_delivery_date: date | None = None


class UpdateSourceItemDemandCommand(BaseModel):
    quantity: float = Field(..., gt=0)
    unit: str = Field(..., min_length=1)
    items_per_unit: float = Field(default=1.0, gt=0)
    high_priority: bool = False
    notify_on_delivery: bool = False
    note: str | None = None
    desired_delivery_date: date | None = None


class SourceItemDemandResult(ResultBase):
    status: str
    # The lifecycle actions the reading user may take now, from the intent
    # table (lifecycle/intents.py); empty where no user is known.
    actions: list[str] = Field(default_factory=list)
    created: datetime
    changed: datetime | None
    quantity: float
    unit: str
    items_per_unit: float
    high_priority: bool
    notify_on_delivery: bool
    note: str | None
    desired_delivery_date: date | None
    creator_id: int
    creator: PublicUserResult | None
    changed_by_id: int | None
    changed_by: PublicUserResult | None
    bought_item_id: int | None
    bought_item: BoughtItemResult | None
    source_item_id: int | None
    source_item: SourceItemResult | None
    lot_id: int
    lot_number: str
    project_id: int
    project_number: str
    project_customer: str
    project_description: str
    project_status: str
    bucket_id: int | None = None
    # Lifecycle intents, read-only (see the SourceItemDemandItem entity).
    canceled_at: datetime | None = None
    fulfilled_manually_at: datetime | None = None
    changes: list[str] = Field(default_factory=list)
