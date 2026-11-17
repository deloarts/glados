"""
HTTP schemas for contacts: create and update requests, the list filter, the
full response and the summary other records embed, and the mail recipients
of a supplier.
"""

from datetime import datetime
from typing import Literal

from fastapi import Query
from pydantic import BaseModel
from pydantic import EmailStr
from pydantic import Field

from src.modules.catalogue.domain.value_objects.contact_organisation_kind import (
    ContactOrganisationKind,
)
from src.modules.catalogue.ports.outbound.repositories.contact_repository import ContactFilterDto
from src.modules.platform.adapters.inbound.api.schemas.base import EntityResponse
from src.modules.platform.adapters.inbound.api.schemas.base import ResponseModel
from src.modules.platform.adapters.inbound.api.schemas.pagination_schema import PageParams
from src.modules.platform.adapters.inbound.api.schemas.user_schema import PublicUserResponse

# ── Request schemas ───────────────────────────────────────────────────


class ContactCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    role: str | None = Field(default=None, max_length=200)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=64)
    mobile: str | None = Field(default=None, max_length=64)
    note: str | None = Field(default=None, max_length=4000)
    # At most one of the two; neither for someone independent.
    customer_id: int | None = None
    supplier_id: int | None = None
    # Only on a supplier's contact.
    receives_request_mails: bool = False
    receives_order_mails: bool = False


class ContactUpdateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    role: str | None = Field(default=None, max_length=200)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=64)
    mobile: str | None = Field(default=None, max_length=64)
    note: str | None = Field(default=None, max_length=4000)
    customer_id: int | None = None
    supplier_id: int | None = None
    receives_request_mails: bool = False
    receives_order_mails: bool = False
    # The edit version the form read; a row changed since answers 409.
    expected_edit_version: int


# ── Response schemas ──────────────────────────────────────────────────


class ContactOrganisationResponse(ResponseModel):
    kind: ContactOrganisationKind
    id: int
    name: str
    archived: bool


class ContactSummaryResponse(EntityResponse):
    """A contact as another record shows it, such as a product's contacts."""

    name: str
    role: str | None
    email: str | None
    phone: str | None
    mobile: str | None
    archived: bool
    anonymised: bool
    organisation: ContactOrganisationResponse | None


class ContactResponse(EntityResponse):
    created: datetime
    changed: datetime | None
    archived: bool
    anonymised_at: datetime | None
    name: str
    role: str | None
    email: str | None
    phone: str | None
    mobile: str | None
    note: str | None
    customer_id: int | None
    supplier_id: int | None
    organisation: ContactOrganisationResponse | None
    receives_request_mails: bool
    receives_order_mails: bool
    creator_id: int
    creator: PublicUserResponse | None
    changed_by_id: int | None
    changed_by: PublicUserResponse | None
    # Sent back as expected_edit_version by an edit of the row.
    edit_version: int = 0


class SupplierMailRecipientResponse(ResponseModel):
    contact_id: int
    name: str
    email: str


class SupplierMailRecipientsResponse(ResponseModel):
    """The flagged contacts each kind of supplier mail goes to. An empty list
    means the supplier's own address for that mail applies."""

    supplier_id: int
    request: list[SupplierMailRecipientResponse]
    order: list[SupplierMailRecipientResponse]


# ── Filter params ─────────────────────────────────────────────────────


class ContactFilterParams(PageParams):
    search: str | None = Query(
        default=None,
        description="Substring match on name, role, e-mail, phone, mobile and organisation",
    )
    name: str | None = Query(default=None, description="Substring match on name and role")
    email: str | None = Query(default=None)
    phone: str | None = Query(default=None, description="Substring match on phone and mobile")
    customer_id: int | None = Query(default=None)
    supplier_id: int | None = Query(default=None)
    organisation_kind: Literal["customer", "supplier", "none"] | None = Query(default=None)
    include_archived: bool = Query(default=False)
    order_by: Literal["name", "organisation", "created", "changed"] | None = Query(default=None)
    order_dir: Literal["asc", "desc"] | None = Query(default=None)

    def to_dto(self) -> ContactFilterDto:
        return ContactFilterDto(**self.model_dump())
