"""
Input commands and output results for product use cases.
"""

from datetime import date
from datetime import datetime

from pydantic import BaseModel

from src.modules.catalogue.application.dto.customer_dto import CustomerResult
from src.modules.platform.application.dto.base import ResultBase
from src.modules.platform.application.dto.user_dto import PublicUserResult

# ── Commands (inbound) ────────────────────────────────────────────────


class CreateProductCommand(BaseModel):
    product_number: str
    customer_id: int | None = None
    description: str | None = None
    designated_user_id: int | None = None
    is_active: bool = True
    designation: str | None = None
    machine_type: str | None = None
    installation_site: str | None = None
    installation_location: str | None = None
    planned_placing_on_market: date | None = None
    legal_basis: str | None = None
    plc_environment_id: int | None = None
    contains_pneumatics: bool = False
    contains_hydraulics: bool = False
    contains_electrics: bool = False
    contains_robotics: bool = False


class UpdateProductCommand(BaseModel):
    product_number: str
    customer_id: int | None = None
    description: str | None = None
    designated_user_id: int | None = None
    is_active: bool | None = None
    designation: str | None = None
    machine_type: str | None = None
    installation_site: str | None = None
    installation_location: str | None = None
    planned_placing_on_market: date | None = None
    legal_basis: str | None = None
    plc_environment_id: int | None = None
    contains_pneumatics: bool = False
    contains_hydraulics: bool = False
    contains_electrics: bool = False
    contains_robotics: bool = False
    # The edit version the client read, checked when given; a row changed
    # since answers 409. The web routes require it, the `pat` API does not.
    expected_edit_version: int | None = None


# ── Results (outbound) ────────────────────────────────────────────────


class ProductResult(ResultBase):
    product_number: str
    customer_id: int | None
    customer: CustomerResult | None
    description: str | None
    designation: str | None
    machine_type: str | None
    installation_site: str | None
    installation_location: str | None
    planned_placing_on_market: date | None
    legal_basis: str | None
    plc_environment_id: int | None
    contains_pneumatics: bool
    contains_hydraulics: bool
    contains_electrics: bool
    contains_robotics: bool
    is_active: bool
    designated_user_id: int
    created: datetime
    archived: bool
    creator_id: int
    creator: PublicUserResult | None
    # The row's edit version, which an edit sends back as expected_edit_version.
    edit_version: int = 0


class ProductRenumberExample(BaseModel):
    old_name: str
    new_name: str


class ProductRenumberImpactResult(BaseModel):
    """What a new product number would affect; see GetProductRenumberImpact."""

    device_count: int
    device_examples: list[ProductRenumberExample]
    released_document_count: int
    export_count: int
