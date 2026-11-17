"""HTTP schemas for supplier master data: capabilities, sourcing options, and contact
information."""

from datetime import date
from datetime import datetime
from datetime import tzinfo
from typing import Generic
from typing import Literal
from typing import TypeVar

from fastapi import Query
from pydantic import BaseModel
from pydantic import Field

from src.modules.catalogue.adapters.inbound.api.schemas.article_group_schema import (
    ArticleGroupResponse,
)
from src.modules.catalogue.adapters.inbound.api.schemas.article_group_schema import (
    ArticleGroupWebResponse,
)
from src.modules.catalogue.adapters.inbound.api.schemas.fabrication_method_schema import (
    FabricationMethodResponse,
)
from src.modules.catalogue.adapters.inbound.api.schemas.fabrication_method_schema import (
    FabricationMethodWebResponse,
)
from src.modules.catalogue.domain.value_objects.supplier_level import SupplierLevel
from src.modules.catalogue.ports.outbound.catalogue_queries import SupplierFilterDto
from src.modules.platform.adapters.inbound.api.schemas.base import EntityResponse
from src.modules.platform.adapters.inbound.api.schemas.base import expand_change_window
from src.modules.platform.adapters.inbound.api.schemas.pagination_schema import PageParams
from src.modules.platform.adapters.inbound.api.schemas.user_schema import PublicUserResponse

TMethod = TypeVar("TMethod")
TGroup = TypeVar("TGroup")

# ── Request schemas ───────────────────────────────────────────────────


class SupplierCreateRequest(BaseModel):
    name: str = Field(..., min_length=1)
    legal_name: str | None = None
    vat_id: str | None = None
    level: SupplierLevel = SupplierLevel.B
    external_lead_time_days: int | None = Field(default=None, ge=0)
    edp_code: str | None = Field(default=None, max_length=16)
    edp_type_number_first: bool = False
    capability_ids: list[int] = Field(default_factory=list)
    article_group_ids: list[int] = Field(default_factory=list)
    street: str | None = None
    city: str | None = None
    country: str | None = None
    postal_code: str | None = None
    email: str | None = None
    phone: str | None = None
    weblink: str | None = None
    order_email: str | None = None
    order_language: str | None = None
    order_template: str | None = None
    request_email: str | None = None
    request_language: str | None = None
    request_template: str | None = None


class SupplierUpdateRequest(BaseModel):
    name: str = Field(..., min_length=1)
    legal_name: str | None = None
    vat_id: str | None = None
    level: SupplierLevel = SupplierLevel.B
    external_lead_time_days: int | None = Field(default=None, ge=0)
    edp_code: str | None = Field(default=None, max_length=16)
    edp_type_number_first: bool = False
    capability_ids: list[int] = Field(default_factory=list)
    article_group_ids: list[int] = Field(default_factory=list)
    street: str | None = None
    city: str | None = None
    country: str | None = None
    postal_code: str | None = None
    email: str | None = None
    phone: str | None = None
    weblink: str | None = None
    order_email: str | None = None
    order_language: str | None = None
    order_template: str | None = None
    request_email: str | None = None
    request_language: str | None = None
    request_template: str | None = None
    # The edit version the form read; a row changed since answers 409.
    expected_edit_version: int


# ── Response schemas ──────────────────────────────────────────────────


class _SupplierFields(EntityResponse, Generic[TMethod, TGroup]):
    created: datetime
    changed: datetime
    archived: bool
    name: str
    legal_name: str | None
    vat_id: str | None
    level: SupplierLevel
    capability_ids: list[int]
    capabilities: list[TMethod] = Field(default_factory=list)
    article_group_ids: list[int]
    article_groups: list[TGroup] = Field(default_factory=list)
    street: str | None
    city: str | None
    country: str | None
    postal_code: str | None
    email: str | None
    phone: str | None
    weblink: str | None
    order_email: str | None
    order_language: str | None
    order_template: str | None
    request_email: str | None
    request_language: str | None
    request_template: str | None
    creator_id: int
    creator: PublicUserResponse | None
    changed_by_id: int | None
    changed_by: PublicUserResponse | None
    # Sent back as expected_edit_version by an edit of the row.
    edit_version: int = 0


# The pat shape: catalogue labels in the request's label languages.
class SupplierResponse(_SupplierFields[FabricationMethodResponse, ArticleGroupResponse]):
    pass


class SupplierWebResponse(_SupplierFields[FabricationMethodWebResponse, ArticleGroupWebResponse]):
    """The web shape: catalogue labels as language maps, plus
    external_lead_time_days, which feeds the scheduler's external lead-time
    forecast, edp_code, which maps the EPLAN Data Portal's manufacturers, and
    edp_type_number_first, which says which portal number becomes order
    code 1. None has a pat use (the SolidWorks add-in never reads or sets
    them)."""

    external_lead_time_days: int | None = None
    edp_code: str | None = None
    edp_type_number_first: bool = False


# ── Filter params ─────────────────────────────────────────────────────


class SupplierFilterParams(PageParams):
    search: str | None = Query(default=None, description="Fuzzy search across all text columns")
    id: int | None = Query(default=None)
    name: str | None = Query(default=None)
    legal_name: str | None = Query(default=None)
    vat_id: str | None = Query(default=None)
    level: SupplierLevel | None = Query(default=None)
    address: str | None = Query(
        default=None, description="Substring match on street, postal code, or city"
    )
    country: str | None = Query(default=None)
    email: str | None = Query(default=None)
    capability_id: int | None = Query(default=None)
    article_group_id: int | None = Query(default=None)
    creator_id: int | None = Query(default=None)
    changed_by_id: int | None = Query(default=None)
    include_archived: bool = Query(default=False)
    created_from: date | datetime | None = Query(default=None)
    created_to: date | datetime | None = Query(default=None)
    changed_from: date | datetime | None = Query(default=None)
    changed_to: date | datetime | None = Query(default=None)
    order_by: Literal["id", "name", "created", "changed"] | None = Query(default=None)
    order_dir: Literal["asc", "desc"] | None = Query(default=None)

    def to_dto(self, zone: tzinfo) -> SupplierFilterDto:
        return SupplierFilterDto(**expand_change_window(self.model_dump(), zone))
