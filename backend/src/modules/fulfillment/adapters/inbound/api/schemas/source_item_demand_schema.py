"""
HTTP schemas for the SourceItemDemandItem aggregate.
"""

from datetime import date
from datetime import datetime
from typing import Literal

from fastapi import Query
from pydantic import BaseModel
from pydantic import Field

from src.modules.catalogue.adapters.inbound.api.schemas.bought_item_schema import (
    BoughtItemWebResponse,
)
from src.modules.catalogue.adapters.inbound.api.schemas.source_item_schema import (
    SourceItemWebResponse,
)
from src.modules.fulfillment.domain.value_objects.source_item_demand_status import (
    SourceItemDemandStatus,
)
from src.modules.fulfillment.ports.outbound.repositories.source_item_demand_repository import (
    SourceItemDemandFilterDto,
)
from src.modules.platform.adapters.inbound.api.schemas.base import EntityResponse
from src.modules.platform.adapters.inbound.api.schemas.pagination_schema import PageParams
from src.modules.platform.adapters.inbound.api.schemas.quantity_fields import PositiveQuantity
from src.modules.platform.adapters.inbound.api.schemas.user_schema import PublicUserResponse
from src.modules.workspace.domain.value_objects.project_status import ProjectStatus
from src.shared_kernel.domain.value_objects.lifecycle_action import LifecycleAction

# ══════════════════════════════════════════════════════════════════════
# SourceItemDemandItem
# ══════════════════════════════════════════════════════════════════════


class SourceItemDemandCreateRequest(BaseModel):
    lot_id: int = Field(..., gt=0)
    quantity: PositiveQuantity
    unit: str = Field(default="pcs", min_length=1)
    items_per_unit: PositiveQuantity = 1.0
    high_priority: bool = False
    notify_on_delivery: bool = False
    note: str | None = None
    desired_delivery_date: date | None = None


class SourceItemDemandUpdateRequest(BaseModel):
    quantity: PositiveQuantity
    unit: str = Field(..., min_length=1)
    items_per_unit: PositiveQuantity = 1.0
    high_priority: bool = False
    notify_on_delivery: bool = False
    note: str | None = None
    desired_delivery_date: date | None = None


class DemandItemBucketRequest(BaseModel):
    bucket_id: int | None = None


class SourceItemDemandResponse(EntityResponse):
    status: SourceItemDemandStatus
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
    bought_item_id: int | None
    bought_item: BoughtItemWebResponse | None
    source_item_id: int | None
    source_item: SourceItemWebResponse | None
    lot_id: int
    lot_number: str
    project_id: int
    project_number: str
    project_customer: str
    project_description: str
    project_status: ProjectStatus
    bucket_id: int | None = None
    # Lifecycle intents, read-only.
    canceled_at: datetime | None = None
    fulfilled_manually_at: datetime | None = None


class SourceItemDemandFilterParams(PageParams):
    ids: list[int] | None = Query(default=None, max_length=200)
    search: str | None = Query(
        default=None,
        max_length=200,
        description="Matches the project, lot, material, bought item or note",
    )
    status: SourceItemDemandStatus | None = Query(default=None)
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
            "Repeatable: lot_id=1&lot_id=2. A single lot_id still binds as a one-element list."
        ),
    )
    bought_item_id: int | None = Query(default=None)
    source_item_id: int | None = Query(default=None)
    project_id: int | None = Query(default=None)
    product_id: int | None = Query(
        default=None, description="Demands of the projects built on this product"
    )
    project_number: str | None = Query(default=None)
    item_dimension: str | None = Query(
        default=None, description="Source item dimension, matches source-item-backed demands only"
    )
    item_material: str | None = Query(
        default=None, description="Source item material, matches source-item-backed demands only"
    )
    item_type: str | None = Query(
        default=None, description="Source item type name, matches source-item-backed demands only"
    )
    order_id: list[int] | None = Query(
        default=None,
        max_length=200,
        description=(
            "Repeatable: order_id=1&order_id=2. Demands holding an allocation "
            "from an order item of any of these orders."
        ),
    )
    creator_id: int | None = Query(default=None)
    changed_by_id: int | None = Query(default=None)
    high_priority: bool | None = Query(default=None)
    desired_from: date | None = Query(default=None)
    desired_to: date | None = Query(default=None)
    # This model is bound at the endpoint as a query-parameter model
    # (`Annotated[SourceItemDemandFilterParams, Query()]`), not via
    # `Depends()`: only the former binds list fields (`ids`, `bucket_id`,
    # `lot_id`, `order_id`) from repeated query keys, see the note on
    # DemandItemFilterParams in
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
            "status",
            "created",
            "changed",
            "desired_delivery_date",
            "bucket_name",
            "project_number",
        ]
        | None
    ) = Query(default=None)
    order_dir: Literal["asc", "desc"] | None = Query(default=None)

    def to_dto(self) -> SourceItemDemandFilterDto:
        return SourceItemDemandFilterDto(**self.model_dump())
