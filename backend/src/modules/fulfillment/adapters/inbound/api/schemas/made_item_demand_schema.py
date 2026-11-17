"""
HTTP schemas for the MadeItemDemandItem aggregate + procurement pipeline.
Mirrors the demand section of bought_item_schema.py.
"""

from datetime import date
from datetime import datetime
from typing import Literal

from fastapi import Query
from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field

from src.modules.catalogue.adapters.inbound.api.schemas.made_item_schema import MadeItemWebResponse
from src.modules.catalogue.domain.value_objects.made_item_status import MadeItemDemandStatus
from src.modules.fulfillment.domain.value_objects.lot_status import LotStatus
from src.modules.fulfillment.domain.value_objects.order_status import OrderItemStatus
from src.modules.fulfillment.domain.value_objects.production_status import ProductionOrderStatus
from src.modules.fulfillment.domain.value_objects.source_item_demand_status import (
    SourceItemDemandStatus,
)
from src.modules.fulfillment.ports.outbound.repositories.made_item_demand_repository import (
    MadeItemDemandFilterDto,
)
from src.modules.platform.adapters.inbound.api.schemas.base import EntityResponse
from src.modules.platform.adapters.inbound.api.schemas.base import ResponseModel
from src.modules.platform.adapters.inbound.api.schemas.pagination_schema import PageParams
from src.modules.platform.adapters.inbound.api.schemas.quantity_fields import PositiveQuantity
from src.modules.platform.adapters.inbound.api.schemas.user_schema import PublicUserResponse
from src.modules.workspace.domain.value_objects.project_status import ProjectStatus
from src.shared_kernel.domain.value_objects.lifecycle_action import LifecycleAction

# ══════════════════════════════════════════════════════════════════════
# MadeItemDemandItem
# ══════════════════════════════════════════════════════════════════════


class MadeItemDemandCreateRequest(BaseModel):
    made_item_id: int = Field(..., gt=0)
    project_id: int = Field(..., gt=0)
    quantity: PositiveQuantity
    unit: str = Field(..., min_length=1)
    items_per_unit: PositiveQuantity = 1.0
    high_priority: bool = False
    notify_on_delivery: bool = False
    note: str | None = None
    desired_delivery_date: date | None = None
    is_alteration: bool = False
    alteration_of_made_item_id: int | None = Field(default=None, gt=0)


class MadeItemDemandUpdateRequest(BaseModel):
    quantity: PositiveQuantity
    unit: str = Field(..., min_length=1)
    items_per_unit: PositiveQuantity = 1.0
    high_priority: bool = False
    notify_on_delivery: bool = False
    note: str | None = None
    desired_delivery_date: date | None = None
    is_alteration: bool = False
    alteration_of_made_item_id: int | None = Field(default=None, gt=0)


class DemandItemBucketRequest(BaseModel):
    bucket_id: int | None = None


class MadeItemDemandResponse(EntityResponse):
    status: MadeItemDemandStatus
    # The lifecycle actions the reading user may take now, computed from the
    # aggregate's intent table; the client gates its buttons on them.
    actions: list[LifecycleAction] = Field(default_factory=list)
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
    creator: PublicUserResponse | None
    changed_by_id: int | None
    changed_by: PublicUserResponse | None
    made_item_id: int
    item_part_number: str
    item_revision: str
    item_article_name: str
    item: MadeItemWebResponse | None = None
    project_id: int
    project_number: str
    project_customer: str
    project_description: str
    project_status: ProjectStatus
    is_alteration: bool = False
    alteration_of_made_item_id: int | None = None
    alteration_of_made_item_part_number: str = ""
    alteration_of_made_item_revision: str = ""
    alteration_of_made_item_article_name: str = ""
    bucket_id: int | None = None
    # Lifecycle intents, read-only.
    canceled_at: datetime | None = None
    fulfilled_manually_at: datetime | None = None


class MadeItemDemandFilterParams(PageParams):
    ids: list[int] | None = Query(default=None, max_length=200)
    search: str | None = Query(default=None, description="Fuzzy search across all text columns")
    status: MadeItemDemandStatus | None = Query(default=None)
    statuses: list[MadeItemDemandStatus] | None = Query(default=None)
    project_id: int | None = Query(default=None)
    product_id: int | None = Query(
        default=None, description="Demands of the projects built on this product"
    )
    project_number: str | None = Query(default=None)
    made_item_id: int | None = Query(default=None)
    item_part_number: str | None = Query(default=None)
    item_article_name: str | None = Query(default=None)
    creator_id: int | None = Query(default=None)
    changed_by_id: int | None = Query(default=None)
    high_priority: bool | None = Query(default=None)
    desired_from: date | None = Query(default=None)
    desired_to: date | None = Query(default=None)
    created_from: date | None = Query(default=None)
    created_to: date | None = Query(default=None)
    ignore_fulfilled: bool | None = Query(default=None)
    ignore_canceled: bool | None = Query(default=None)
    not_fully_allocated: bool | None = Query(
        default=None,
        description=(
            "Only demands with quantity left to allocate (what the UI renders as "
            "open/partially allocated). Derived from allocation quantities, not "
            "from the coarse stored status, 'allocated' covers both partial and "
            "full coverage."
        ),
    )
    lot_id: list[int] | None = Query(
        default=None,
        max_length=200,
        description=(
            "Repeatable: lot_id=1&lot_id=2. Demands holding an allocation from any of these lots."
        ),
    )
    process_fabrication_method_id: list[int] | None = Query(
        default=None,
        max_length=200,
        description=(
            "Repeatable. Demands whose made item has a routing process with any of "
            "these fabrication methods; combined any-of with "
            "process_inspection_method_id."
        ),
    )
    process_inspection_method_id: list[int] | None = Query(
        default=None,
        max_length=200,
        description=(
            "Repeatable. Demands whose made item has a routing process with any of "
            "these inspection methods; combined any-of with "
            "process_fabrication_method_id."
        ),
    )
    # This model is bound at the endpoint as a query-parameter model
    # (`Annotated[MadeItemDemandFilterParams, Query()]`), not via `Depends()`:
    # only the former binds list fields (`ids`, `statuses`, `bucket_id`, the
    # lot and process method lists) from repeated query keys; see the note
    # on DemandItemFilterParams in
    # bought_item_schema.py. Guarded by
    # tests/integration/test_api_list_query_params.py.
    bucket_id: list[int] | None = Query(
        default=None,
        max_length=200,
        description=(
            "Repeatable: bucket_id=1&bucket_id=2. Buckets only group demands for "
            "display; no business rule depends on them."
        ),
    )
    include_unbucketed: bool | None = Query(default=None)
    order_by: (
        Literal[
            "id",
            "article_name",
            "desired_delivery_date",
            "created",
            "bucket_name",
            "project_number",
        ]
        | None
    ) = Query(default=None)
    order_dir: Literal["asc", "desc"] | None = Query(default=None)

    def to_dto(self) -> MadeItemDemandFilterDto:
        return MadeItemDemandFilterDto(**self.model_dump())


# ══════════════════════════════════════════════════════════════════════
# Batch demand import (Excel)
#
# Mirrors the "Batch demand import (Excel)" section of bought_item_schema.py.
# ══════════════════════════════════════════════════════════════════════


class MadeItemBatchDemandRowSchema(BaseModel):
    """One spreadsheet row. Deliberately permissive: a blank or garbled cell
    comes back as an invalid row with a message instead of failing the whole
    request with a 422."""

    row_index: int
    project_number: str | None = None
    quantity: float | None = None
    part_number: str | None = None
    revision: str | None = None
    article_name: str | None = None
    desired_delivery_date: date | None = None
    note: str | None = None


class ValidateBatchMadeItemDemandsRequest(BaseModel):
    rows: list[MadeItemBatchDemandRowSchema]


class CommitBatchMadeItemDemandsRequest(BaseModel):
    rows: list[MadeItemBatchDemandRowSchema]


class MadeItemFieldDivergenceResponse(ResponseModel):
    field: Literal["article_name", "status"]
    db_value: str | None
    file_value: str | None


class MadeItemRowValidationResponse(ResponseModel):
    row_index: int
    row_status: Literal["matched", "not_found", "ambiguous", "unresolved_reference", "invalid"]
    match_source: Literal["part_number_revision"] | None = None
    matched_item: MadeItemWebResponse | None = None
    divergences: list[MadeItemFieldDivergenceResponse] = Field(default_factory=list)
    resolved_project_id: int | None = None
    errors: list[str] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class ValidateBatchMadeItemDemandsResponse(ResponseModel):
    results: list[MadeItemRowValidationResponse]
    all_valid: bool

    model_config = ConfigDict(from_attributes=True)


class CommitBatchMadeItemDemandsResponse(ResponseModel):
    created_demand_ids: list[int] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


# ══════════════════════════════════════════════════════════════════════
# Procurement pipeline
# ══════════════════════════════════════════════════════════════════════


class MadeItemPipelineRowResponse(ResponseModel):
    demand_item_id: int
    status: MadeItemDemandStatus
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


class MadeItemPipelinePageResponse(ResponseModel):
    items: list[MadeItemPipelineRowResponse] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


# ══════════════════════════════════════════════════════════════════════
# Cancelation impact
# ══════════════════════════════════════════════════════════════════════


class CancelImpactProductionOrderResponse(ResponseModel):
    production_order_id: int
    production_order_number: str
    status: ProductionOrderStatus
    quantity: float
    quantity_completed: float
    machine_id: int | None
    machine_name: str
    lot_position_sequence: int
    will_cancel: bool
    keep_reason: str | None = None

    model_config = ConfigDict(from_attributes=True)


class CancelImpactOrderItemResponse(ResponseModel):
    order_item_id: int
    order_id: int
    order_number: str
    position: int
    status: OrderItemStatus
    quantity: float
    quantity_delivered: float
    unit: str
    supplier_name: str
    item_article_name: str
    lot_position_sequence: int | None = None
    will_cancel: bool
    keep_reason: str | None = None

    model_config = ConfigDict(from_attributes=True)


class CancelImpactSourceItemDemandResponse(ResponseModel):
    demand_id: int
    status: SourceItemDemandStatus
    quantity: float
    unit: str
    item_article_name: str
    will_cancel: bool
    keep_reason: str | None = None
    order_items: list[CancelImpactOrderItemResponse] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class CancelImpactLotResponse(ResponseModel):
    lot_id: int
    lot_number: str
    status: LotStatus
    quantity: float
    quantity_completed: float
    allocated_quantity: float
    will_cancel: bool
    # The lot already made good pieces: its cancel, and the demand's, is refused.
    cancel_refused: bool = False
    keep_reason: str | None = None
    other_demand_ids: list[int] = Field(default_factory=list)
    source_item_demand: CancelImpactSourceItemDemandResponse | None = None
    production_orders: list[CancelImpactProductionOrderResponse] = Field(default_factory=list)
    order_items: list[CancelImpactOrderItemResponse] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class MadeItemDemandCancelImpactResponse(ResponseModel):
    demand_item_id: int
    status: MadeItemDemandStatus
    quantity: float
    unit: str
    item_part_number: str
    item_revision: str
    item_article_name: str
    project_number: str
    can_cancel_lots: bool = True
    lots: list[CancelImpactLotResponse] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)
