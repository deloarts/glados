"""HTTP schemas for the Project catalogue aggregate."""

from datetime import date
from datetime import datetime
from typing import Literal

from fastapi import Query
from pydantic import BaseModel
from pydantic import Field

from src.modules.catalogue.adapters.inbound.api.schemas.customer_schema import CustomerResponse
from src.modules.platform.adapters.inbound.api.schemas.base import EntityResponse
from src.modules.platform.adapters.inbound.api.schemas.base import ResponseModel
from src.modules.platform.adapters.inbound.api.schemas.pagination_schema import PageParams
from src.modules.platform.adapters.inbound.api.schemas.user_schema import PublicUserResponse
from src.modules.workspace.adapters.inbound.api.schemas.product_schema import ProductResponse
from src.modules.workspace.domain.value_objects.project_status import ProjectStatus
from src.modules.workspace.ports.outbound.workspace_queries import ProjectFilterDto

# ── Request schemas ───────────────────────────────────────────────────


class ProjectCreateRequest(BaseModel):
    project_number: str = Field(..., min_length=1)
    customer_id: int | None = None
    product_id: int | None = None
    description: str | None = None
    designated_user_id: int | None = Field(default=None, gt=0)
    status: ProjectStatus = ProjectStatus.ACTIVE
    production_time_budget: int | None = Field(default=None, ge=0)
    required_delivery_date_made: date | None = None
    required_delivery_date_bought: date | None = None


class ProjectUpdateRequest(BaseModel):
    project_number: str = Field(..., min_length=1)
    customer_id: int | None = None
    product_id: int | None = None
    description: str | None = None
    designated_user_id: int | None = Field(default=None, gt=0)
    status: ProjectStatus | None = None
    production_time_budget: int | None = Field(default=None, ge=0)
    required_delivery_date_made: date | None = None
    required_delivery_date_bought: date | None = None
    # If the corresponding date above changed to a new non-null value,
    # bulk-update it onto all non-completed demands of this project.
    propagate_delivery_date_made: bool = False
    propagate_delivery_date_bought: bool = False
    # The edit version the client read; a project edited since answers 409.
    expected_edit_version: int


# ── Response schemas ──────────────────────────────────────────────────


class ProjectResponse(EntityResponse):
    project_number: str
    customer_id: int | None
    customer: CustomerResponse | None
    product_id: int | None
    product: ProductResponse | None
    description: str | None
    status: ProjectStatus
    designated_user_id: int
    created: datetime
    changed: datetime | None
    creator_id: int
    creator: PublicUserResponse | None
    changed_by_id: int | None
    changed_by: PublicUserResponse | None
    production_time_budget: int | None
    required_delivery_date_made: date | None
    required_delivery_date_bought: date | None


# ── Filter params ─────────────────────────────────────────────────────


class ProjectFilterParams(PageParams):
    search: str | None = Query(default=None, description="Fuzzy search across all text columns")
    id: int | None = Query(default=None)
    ids: list[int] | None = Query(default=None, max_length=200)
    project_number: str | None = Query(default=None)
    customer_id: int | None = Query(default=None)
    product_id: int | None = Query(default=None)
    description: str | None = Query(default=None)
    status: ProjectStatus | None = Query(default=None)
    designated_user_id: int | None = Query(default=None)
    creator_id: int | None = Query(default=None)
    changed_by_id: int | None = Query(default=None)
    created_from: date | None = Query(default=None)
    created_to: date | None = Query(default=None)
    required_delivery_date_made_from: date | None = Query(default=None)
    required_delivery_date_made_to: date | None = Query(default=None)
    required_delivery_date_bought_from: date | None = Query(default=None)
    required_delivery_date_bought_to: date | None = Query(default=None)
    order_by: Literal["id", "project_number", "created"] | None = Query(default=None)
    order_dir: Literal["asc", "desc"] | None = Query(default=None)

    def to_dto(self) -> ProjectFilterDto:
        return ProjectFilterDto(**self.model_dump())


# ── Summary response schemas ──────────────────────────────────────────


class ProjectCostBySupplier(ResponseModel):
    supplier_id: int
    supplier_name: str
    ordered_cost: int
    delivered_cost: int


class ProjectSummaryResponse(ResponseModel):
    total_ordered_cost: int
    total_delivered_cost: int
    order_count: int
    cost_by_supplier: list[ProjectCostBySupplier]
    demand_counts: dict[str, int]
