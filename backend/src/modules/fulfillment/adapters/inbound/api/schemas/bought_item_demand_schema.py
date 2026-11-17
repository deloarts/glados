"""
Request and response schemas of the demand items of bought items, the
procurement pipeline and the batch demand import.
"""

from datetime import date
from datetime import datetime
from typing import Literal

from fastapi import Query
from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field

from src.modules.catalogue.adapters.inbound.api.schemas.bought_item_schema import (
    BoughtItemWebResponse,
)
from src.modules.catalogue.domain.value_objects.bought_item_status import BoughtItemDemandStatus
from src.modules.fulfillment.ports.outbound.repositories.bought_item_demand_repository import (
    DemandItemFilterDto,
)
from src.modules.platform.adapters.inbound.api.schemas.base import EntityResponse
from src.modules.platform.adapters.inbound.api.schemas.base import ResponseModel
from src.modules.platform.adapters.inbound.api.schemas.pagination_schema import PageParams
from src.modules.platform.adapters.inbound.api.schemas.quantity_fields import PositiveQuantity
from src.modules.platform.adapters.inbound.api.schemas.user_schema import PublicUserResponse
from src.modules.workspace.domain.value_objects.project_status import ProjectStatus
from src.shared_kernel.domain.value_objects.lifecycle_action import LifecycleAction


class DemandItemCreateRequest(BaseModel):
    item_id: int = Field(..., gt=0)
    project_id: int = Field(..., gt=0)
    quantity: PositiveQuantity
    unit: str = Field(..., min_length=1)
    items_per_unit: PositiveQuantity = 1.0
    high_priority: bool = False
    notify_on_delivery: bool = False
    note: str | None = None
    desired_delivery_date: date | None = None


class DemandItemUpdateRequest(BaseModel):
    quantity: PositiveQuantity
    unit: str = Field(..., min_length=1)
    items_per_unit: PositiveQuantity = 1.0
    high_priority: bool = False
    notify_on_delivery: bool = False
    note: str | None = None
    desired_delivery_date: date | None = None


class DemandItemBucketRequest(BaseModel):
    bucket_id: int | None = None


class DemandItemResponse(EntityResponse):
    status: BoughtItemDemandStatus
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
    item_id: int
    item_order_code_1: str
    item_article_name: str
    item: BoughtItemWebResponse | None = None
    project_id: int
    project_number: str
    project_customer: str
    project_description: str
    project_status: ProjectStatus
    bucket_id: int | None
    # Lifecycle intents, read-only.
    canceled_at: datetime | None = None
    fulfilled_manually_at: datetime | None = None


class DemandItemFilterParams(PageParams):
    ids: list[int] | None = Query(default=None, max_length=200)
    search: str | None = Query(default=None, description="Fuzzy search across all text columns")
    status: BoughtItemDemandStatus | None = Query(default=None)
    project_id: int | None = Query(default=None)
    product_id: int | None = Query(
        default=None, description="Demands of the projects built on this product"
    )
    project_number: str | None = Query(default=None)
    item_id: int | None = Query(default=None)
    item_order_code_1: str | None = Query(default=None)
    item_order_code_2: str | None = Query(default=None)
    item_article_name: str | None = Query(default=None)
    item_part_number: str | None = Query(default=None)
    item_manufacturer_name: str | None = Query(default=None)
    item_manufacturer_id: int | None = Query(default=None)
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
    order_id: list[int] | None = Query(
        default=None,
        max_length=200,
        description=(
            "Repeatable: order_id=1&order_id=2. Demands holding an allocation "
            "from an order item of any of these orders."
        ),
    )
    # This model is bound at the endpoint as a query-parameter model
    # (`Annotated[DemandItemFilterParams, Query()]`), not via `Depends()`:
    # only the former binds list fields (`ids`, `bucket_id`, `order_id`)
    # from repeated query keys: under `Depends()` FastAPI classifies them as a request
    # body on the GET and they silently arrive as None. Guarded by
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
            "manufacturer_name",
            "desired_delivery_date",
            "created",
            "bucket_name",
            "project_number",
        ]
        | None
    ) = Query(default=None)
    order_dir: Literal["asc", "desc"] | None = Query(default=None)

    def to_dto(self) -> DemandItemFilterDto:
        return DemandItemFilterDto(**self.model_dump())


class BatchDemandRowSchema(BaseModel):
    """One spreadsheet row. Deliberately permissive: a blank or garbled cell
    comes back as an invalid row with a message instead of failing the whole
    request with a 422."""

    row_index: int
    project_number: str | None = None
    quantity: float | None = None
    unit: str | None = None
    part_number: str | None = None
    article_name: str | None = None
    order_code: str | None = None
    manufacturer_name: str | None = None
    desired_delivery_date: date | None = None
    note: str | None = None


class ValidateBatchDemandsRequest(BaseModel):
    rows: list[BatchDemandRowSchema]


class CommitBatchDemandsRequest(BaseModel):
    rows: list[BatchDemandRowSchema]


class FieldDivergenceResponse(ResponseModel):
    field: Literal["article_name", "manufacturer_name", "order_code", "part_number"]
    db_value: str | None
    file_value: str | None


class RowValidationResponse(ResponseModel):
    row_index: int
    row_status: Literal["matched", "not_found", "ambiguous", "unresolved_reference", "invalid"]
    match_source: Literal["part_number", "order_code_manufacturer"] | None = None
    matched_item: BoughtItemWebResponse | None = None
    divergences: list[FieldDivergenceResponse] = Field(default_factory=list)
    resolved_project_id: int | None = None
    errors: list[str] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class ValidateBatchDemandsResponse(ResponseModel):
    results: list[RowValidationResponse]
    all_valid: bool

    model_config = ConfigDict(from_attributes=True)


class CommitBatchDemandsResponse(ResponseModel):
    created_demand_ids: list[int] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class PipelineRowResponse(ResponseModel):
    demand_item_id: int
    status: BoughtItemDemandStatus
    high_priority: bool
    item_id: int
    item_order_code_1: str
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
    supplier_names: list[str] = Field(default_factory=list)
    order_numbers: list[str] = Field(default_factory=list)
    expected_delivery_dates: list[date] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class PipelinePageResponse(ResponseModel):
    items: list[PipelineRowResponse] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)
