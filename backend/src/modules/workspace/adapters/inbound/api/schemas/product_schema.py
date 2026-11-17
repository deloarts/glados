"""HTTP schemas for the Product catalogue aggregate."""

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
from src.modules.workspace.ports.outbound.repositories.product_repository import ProductFilterDto

LegalBasis = Literal["directive", "regulation"]

# ── Request schemas ───────────────────────────────────────────────────


class ProductCreateRequest(BaseModel):
    product_number: str = Field(..., min_length=1)
    customer_id: int | None = None
    description: str | None = None
    designated_user_id: int | None = Field(default=None, gt=0)
    is_active: bool = True
    designation: str | None = Field(default=None, max_length=200)
    machine_type: str | None = Field(default=None, max_length=200)
    installation_site: str | None = Field(default=None, max_length=200)
    installation_location: str | None = Field(default=None, max_length=200)
    planned_placing_on_market: date | None = None
    legal_basis: LegalBasis | None = None
    plc_environment_id: int | None = Field(default=None, gt=0)
    contains_pneumatics: bool = False
    contains_hydraulics: bool = False
    contains_electrics: bool = False
    contains_robotics: bool = False


class ProductUpdateRequest(BaseModel):
    product_number: str = Field(..., min_length=1)
    customer_id: int | None = None
    description: str | None = None
    designated_user_id: int | None = Field(default=None, gt=0)
    is_active: bool | None = None
    designation: str | None = Field(default=None, max_length=200)
    machine_type: str | None = Field(default=None, max_length=200)
    installation_site: str | None = Field(default=None, max_length=200)
    installation_location: str | None = Field(default=None, max_length=200)
    planned_placing_on_market: date | None = None
    legal_basis: LegalBasis | None = None
    plc_environment_id: int | None = Field(default=None, gt=0)
    contains_pneumatics: bool = False
    contains_hydraulics: bool = False
    contains_electrics: bool = False
    contains_robotics: bool = False
    # The edit version the form read; a row changed since answers 409.
    expected_edit_version: int


# ── Response schemas ──────────────────────────────────────────────────


class ProductResponse(EntityResponse):
    product_number: str
    customer_id: int | None
    customer: CustomerResponse | None
    description: str | None
    is_active: bool
    designated_user_id: int
    created: datetime
    archived: bool
    creator_id: int
    creator: PublicUserResponse | None
    # Sent back as expected_edit_version by an edit of the row.
    edit_version: int = 0


# ── Filter params ─────────────────────────────────────────────────────


class ProductFilterParams(PageParams):
    search: str | None = Query(default=None, description="Fuzzy search across all text columns")
    id: int | None = Query(default=None)
    product_number: str | None = Query(default=None)
    customer_id: int | None = Query(default=None)
    description: str | None = Query(default=None)
    is_active: bool | None = Query(default=None)
    designated_user_id: int | None = Query(default=None)
    creator_id: int | None = Query(default=None)
    created_from: date | None = Query(default=None)
    created_to: date | None = Query(default=None)
    include_archived: bool = Query(default=False)
    order_by: Literal["id", "product_number", "created"] | None = Query(default=None)
    order_dir: Literal["asc", "desc"] | None = Query(default=None)

    def to_dto(self) -> ProductFilterDto:
        return ProductFilterDto(**self.model_dump())


class ProductRenumberExampleResponse(ResponseModel):
    old_name: str
    new_name: str


class ProductRenumberImpactResponse(ResponseModel):
    device_count: int
    device_examples: list[ProductRenumberExampleResponse]
    released_document_count: int
    export_count: int
