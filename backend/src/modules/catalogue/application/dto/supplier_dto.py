"""
Input commands and output results for supplier use cases.
These cross the application boundary, not the same as API schemas.
"""

from datetime import datetime

from pydantic import BaseModel
from pydantic import Field

from src.modules.catalogue.application.dto.article_group_dto import ArticleGroupResult
from src.modules.catalogue.application.dto.fabrication_method_dto import FabricationMethodResult
from src.modules.platform.application.dto.base import ResultBase
from src.modules.platform.application.dto.user_dto import PublicUserResult

# ── Commands (inbound) ────────────────────────────────────────────────


class CreateSupplierCommand(BaseModel):
    name: str = Field(..., min_length=1)
    legal_name: str | None = None
    vat_id: str | None = None
    level: str = "B"
    external_lead_time_days: int | None = None
    edp_code: str | None = None
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


class UpdateSupplierCommand(BaseModel):
    name: str = Field(..., min_length=1)
    legal_name: str | None = None
    vat_id: str | None = None
    level: str = "B"
    external_lead_time_days: int | None = None
    edp_code: str | None = None
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
    # The edit version the client read, checked when given; a row changed
    # since answers 409. The web routes require it, the `pat` API does not.
    expected_edit_version: int | None = None


# ── Results (outbound) ────────────────────────────────────────────────


class SupplierResult(ResultBase):
    created: datetime
    changed: datetime
    archived: bool
    name: str
    legal_name: str | None
    vat_id: str | None
    level: str
    external_lead_time_days: int | None = None
    edp_code: str | None = None
    edp_type_number_first: bool = False
    capability_ids: list[int]
    capabilities: list[FabricationMethodResult] = Field(default_factory=list)
    article_group_ids: list[int]
    article_groups: list[ArticleGroupResult] = Field(default_factory=list)
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
    creator: PublicUserResult | None
    changed_by_id: int | None
    changed_by: PublicUserResult | None
    # The row's edit version, which an edit sends back as expected_edit_version.
    edit_version: int = 0
