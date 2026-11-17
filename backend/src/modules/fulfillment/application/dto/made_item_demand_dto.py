"""
DTOs for the MadeItemDemandItem aggregate + the made-item procurement
pipeline. Field-for-field mirror of the demand section of
bought_item_dto.py, including batch import (see the "Batch demand import"
section below, mirroring bought_item_dto.py's own).
"""

from datetime import date
from datetime import datetime
from typing import Literal

from pydantic import BaseModel
from pydantic import Field

from src.modules.catalogue.application.dto.made_item_dto import MadeItemResult
from src.modules.platform.application.dto.base import ResultBase
from src.modules.platform.application.dto.user_dto import PublicUserResult

# ══════════════════════════════════════════════════════════════════════
# MadeItemDemandItem
# ══════════════════════════════════════════════════════════════════════


class CreateMadeItemDemandCommand(BaseModel):
    made_item_id: int = Field(..., gt=0)
    project_id: int = Field(..., gt=0)
    quantity: float = Field(..., gt=0)
    unit: str = Field(..., min_length=1)
    items_per_unit: float = Field(default=1.0, gt=0)
    high_priority: bool = False
    notify_on_delivery: bool = False
    note: str | None = None
    desired_delivery_date: date | None = None
    is_alteration: bool = False
    alteration_of_made_item_id: int | None = Field(default=None, gt=0)


class UpdateMadeItemDemandCommand(BaseModel):
    quantity: float = Field(..., gt=0)
    unit: str = Field(..., min_length=1)
    items_per_unit: float = Field(default=1.0, gt=0)
    high_priority: bool = False
    notify_on_delivery: bool = False
    note: str | None = None
    desired_delivery_date: date | None = None
    is_alteration: bool = False
    alteration_of_made_item_id: int | None = Field(default=None, gt=0)


class MadeItemDemandItemResult(ResultBase):
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
    made_item_id: int
    item_part_number: str
    item_revision: str
    item_article_name: str
    item: MadeItemResult | None = None
    project_id: int
    project_number: str
    project_customer: str
    project_description: str
    project_status: str
    is_alteration: bool = False
    alteration_of_made_item_id: int | None = None
    alteration_of_made_item_part_number: str = ""
    alteration_of_made_item_revision: str = ""
    alteration_of_made_item_article_name: str = ""
    bucket_id: int | None = None
    # Lifecycle intents, read-only (see the MadeItemDemandItem entity).
    canceled_at: datetime | None = None
    fulfilled_manually_at: datetime | None = None


# ══════════════════════════════════════════════════════════════════════
# Batch demand import (Excel)
#
# Mirrors the "Batch demand import (Excel)" section of bought_item_dto.py.
# Lookup-only importer: a row's catalogue item is *found* (by part number +
# revision), never created or updated. Divergence between the file and the
# matched catalogue item (article name, status) is reported as a warning
# only and never applied. Unlike the bought importer there is no fallback
# lookup key and no unit column (made-item demands are always "PCS").
# ══════════════════════════════════════════════════════════════════════


class MadeItemBatchDemandRowInput(BaseModel):
    """
    Intentionally permissive (no min_length/gt constraints on the row's own
    data): a blank/garbled cell in one Excel row must surface as a per-row
    'invalid' status with a specific message, not reject the entire batch
    request with a 422.
    """

    row_index: int
    project_number: str | None = None
    quantity: float | None = None
    part_number: str | None = None
    revision: str | None = None
    article_name: str | None = None
    desired_delivery_date: date | None = None
    note: str | None = None


class FieldDivergence(BaseModel):
    field: Literal["article_name", "status"]
    db_value: str | None
    file_value: str | None


class MadeItemRowValidationResult(BaseModel):
    row_index: int
    row_status: Literal["matched", "not_found", "ambiguous", "unresolved_reference", "invalid"]
    match_source: Literal["part_number_revision"] | None = None
    matched_item: MadeItemResult | None = None
    divergences: list[FieldDivergence] = Field(default_factory=list)
    resolved_project_id: int | None = None
    errors: list[str] = Field(default_factory=list)


class ValidateBatchMadeItemDemandsResult(BaseModel):
    results: list[MadeItemRowValidationResult]
    all_valid: bool


class CommitBatchMadeItemDemandsResult(BaseModel):
    created_demand_ids: list[int] = Field(default_factory=list)


# ══════════════════════════════════════════════════════════════════════
# Cancelation impact
#
# Canceling a made-item demand takes down everything that exists only to
# fulfill it, the lots allocated to it, their raw-material demands, and
# the production orders / supplier order items those lots' positions were
# committed to. The impact tree below is what the confirmation dialog
# shows before the user commits to that, and the same collector produces
# it for both the preview and the cancel itself, so what was shown is
# exactly what gets canceled.
#
# Every level carries will_cancel + keep_reason rather than being filtered
# down to only the doomed rows: "this delivered order item stays" is
# information the user needs just as much as "this production order goes".
# ══════════════════════════════════════════════════════════════════════


class CancelImpactProductionOrderResult(BaseModel):
    production_order_id: int
    production_order_number: str
    status: str
    quantity: float
    quantity_completed: float
    machine_id: int | None
    machine_name: str
    lot_position_sequence: int
    will_cancel: bool
    keep_reason: str | None = None


class CancelImpactOrderItemResult(BaseModel):
    order_item_id: int
    order_id: int
    order_number: str
    position: int
    status: str
    quantity: float
    quantity_delivered: float
    unit: str
    supplier_name: str
    item_article_name: str
    lot_position_sequence: int | None = None
    will_cancel: bool
    keep_reason: str | None = None


class CancelImpactSourceItemDemandResult(BaseModel):
    demand_id: int
    status: str
    quantity: float
    unit: str
    item_article_name: str
    will_cancel: bool
    keep_reason: str | None = None
    # Raw-material purchase lines already covering this demand. Never
    # canceled here, material on order with a supplier is a commitment
    # this cascade has no business unwinding, but listed so the user can
    # follow up with procurement themselves.
    order_items: list[CancelImpactOrderItemResult] = Field(default_factory=list)


class CancelImpactLotResult(BaseModel):
    lot_id: int
    lot_number: str
    status: str
    quantity: float
    quantity_completed: float
    allocated_quantity: float  # how much of THIS demand the lot covers
    will_cancel: bool
    # The lot would be canceled, but it already made good pieces, so its
    # cancel, and the demand's with it, is refused until it is force-completed.
    cancel_refused: bool = False
    keep_reason: str | None = None
    # Other still-live demands allocated to the same lot, the reason a
    # lot survives its demand's cancelation.
    other_demand_ids: list[int] = Field(default_factory=list)
    source_item_demand: CancelImpactSourceItemDemandResult | None = None
    production_orders: list[CancelImpactProductionOrderResult] = Field(default_factory=list)
    order_items: list[CancelImpactOrderItemResult] = Field(default_factory=list)


class CancelMadeItemDemandImpactResult(BaseModel):
    demand_item_id: int
    status: str
    quantity: float
    unit: str
    item_part_number: str
    item_revision: str
    item_article_name: str
    project_number: str
    # False when the actor lacks MANAGE_LOTS while lots would have to be
    # canceled, the dialog can say so up front instead of letting the
    # user confirm into a 403.
    can_cancel_lots: bool = True
    lots: list[CancelImpactLotResult] = Field(default_factory=list)

    @property
    def has_impact(self) -> bool:
        return bool(self.lots)


# ══════════════════════════════════════════════════════════════════════
# Procurement pipeline (mirrors the bought-item pipeline)
# ══════════════════════════════════════════════════════════════════════


class MadeItemPipelineRowResult(BaseModel):
    demand_item_id: int
    status: str
    high_priority: bool
    made_item_id: int
    item_part_number: str
    item_revision: str
    item_article_name: str
    project_id: int
    project_number: str
    unit: str
    total: float
    allocated: float
    ordered: float
    delivered: float
    fulfilled_from_stock: float
    remaining: float
    is_fully_allocated: bool
    is_fully_delivered: bool


class MadeItemPipelineResult(BaseModel):
    items: list[MadeItemPipelineRowResult] = Field(default_factory=list)
