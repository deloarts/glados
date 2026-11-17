"""
HTTP schemas for customer creation, updates, filtering, and responses.
"""

from datetime import date
from datetime import datetime
from typing import Literal

from fastapi import Query
from pydantic import BaseModel
from pydantic import Field

from src.modules.catalogue.ports.outbound.repositories.customer_repository import CustomerFilterDto
from src.modules.platform.adapters.inbound.api.schemas.base import EntityResponse
from src.modules.platform.adapters.inbound.api.schemas.pagination_schema import PageParams
from src.modules.platform.adapters.inbound.api.schemas.user_schema import PublicUserResponse

# ── Request schemas ───────────────────────────────────────────────────


class CustomerCreateRequest(BaseModel):
    name: str = Field(..., min_length=1)
    legal_name: str | None = None
    vat_id: str | None = None
    level: str = Field(default="B", pattern="^[ABC]$")
    street: str | None = None
    city: str | None = None
    country: str | None = Field(default=None, min_length=2, max_length=2)
    postal_code: str | None = None
    email: str | None = None
    phone: str | None = None
    weblink: str | None = None


class CustomerUpdateRequest(BaseModel):
    name: str = Field(..., min_length=1)
    legal_name: str | None = None
    vat_id: str | None = None
    level: str = Field(..., pattern="^[ABC]$")
    street: str | None = None
    city: str | None = None
    country: str | None = Field(default=None, min_length=2, max_length=2)
    postal_code: str | None = None
    email: str | None = None
    phone: str | None = None
    weblink: str | None = None
    # The edit version the form read; a row changed since answers 409.
    expected_edit_version: int


# ── Response schemas ──────────────────────────────────────────────────


class CustomerResponse(EntityResponse):
    created: datetime
    changed: datetime | None
    archived: bool
    name: str
    legal_name: str | None
    vat_id: str | None
    level: str
    street: str | None
    city: str | None
    country: str | None
    postal_code: str | None
    email: str | None
    phone: str | None
    weblink: str | None
    creator_id: int
    creator: PublicUserResponse | None
    changed_by_id: int | None
    changed_by: PublicUserResponse | None
    # Sent back as expected_edit_version by an edit of the row.
    edit_version: int = 0


# ── Filter params ─────────────────────────────────────────────────────


class CustomerFilterParams(PageParams):
    search: str | None = Query(default=None, description="Fuzzy search across all text columns")
    id: int | None = Query(default=None)
    name: str | None = Query(default=None)
    legal_name: str | None = Query(default=None)
    vat_id: str | None = Query(default=None)
    level: str | None = Query(default=None)
    address: str | None = Query(
        default=None, description="Substring match on street, postal code, or city"
    )
    country: str | None = Query(default=None)
    email: str | None = Query(default=None)
    creator_id: int | None = Query(default=None)
    changed_by_id: int | None = Query(default=None)
    created_from: date | None = Query(default=None)
    created_to: date | None = Query(default=None)
    changed_from: date | None = Query(default=None)
    changed_to: date | None = Query(default=None)
    include_archived: bool = Query(default=False)
    order_by: Literal["id", "name", "created", "changed"] | None = Query(default=None)
    order_dir: Literal["asc", "desc"] | None = Query(default=None)

    def to_dto(self) -> CustomerFilterDto:
        return CustomerFilterDto(**self.model_dump())
