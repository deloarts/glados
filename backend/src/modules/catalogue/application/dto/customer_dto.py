"""
Input commands and output results for customer use cases.
"""

from datetime import datetime

from pydantic import BaseModel

from src.modules.platform.application.dto.base import ResultBase
from src.modules.platform.application.dto.user_dto import PublicUserResult

# ── Commands (inbound) ────────────────────────────────────────────────


class CreateCustomerCommand(BaseModel):
    name: str
    legal_name: str | None = None
    vat_id: str | None = None
    level: str = "B"
    street: str | None = None
    city: str | None = None
    country: str | None = None
    postal_code: str | None = None
    email: str | None = None
    phone: str | None = None
    weblink: str | None = None


class UpdateCustomerCommand(BaseModel):
    name: str
    legal_name: str | None = None
    vat_id: str | None = None
    level: str
    street: str | None = None
    city: str | None = None
    country: str | None = None
    postal_code: str | None = None
    email: str | None = None
    phone: str | None = None
    weblink: str | None = None
    # The edit version the client read, checked when given; a row changed
    # since answers 409. The web routes require it, the `pat` API does not.
    expected_edit_version: int | None = None


# ── Results (outbound) ────────────────────────────────────────────────


class CustomerResult(ResultBase):
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
    creator: PublicUserResult | None
    changed_by_id: int | None
    changed_by: PublicUserResult | None
    # The row's edit version, which an edit sends back as expected_edit_version.
    edit_version: int = 0
