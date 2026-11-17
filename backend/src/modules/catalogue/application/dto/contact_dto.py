"""
Input commands and output results for contact use cases. The summary and
the organisation results are public, for the modules that show a contact
next to their own records, such as the contacts of a product.
"""

from datetime import datetime

from pydantic import BaseModel

from src.modules.catalogue.domain.value_objects.contact_organisation_kind import (
    ContactOrganisationKind,
)
from src.modules.platform.application.dto.base import ResultBase
from src.modules.platform.application.dto.base import ResultModel
from src.modules.platform.application.dto.user_dto import PublicUserResult

# ── Commands (inbound) ────────────────────────────────────────────────


class CreateContactCommand(BaseModel):
    name: str
    role: str | None = None
    email: str | None = None
    phone: str | None = None
    mobile: str | None = None
    note: str | None = None
    customer_id: int | None = None
    supplier_id: int | None = None
    receives_request_mails: bool = False
    receives_order_mails: bool = False


class UpdateContactCommand(BaseModel):
    name: str
    role: str | None = None
    email: str | None = None
    phone: str | None = None
    mobile: str | None = None
    note: str | None = None
    customer_id: int | None = None
    supplier_id: int | None = None
    receives_request_mails: bool = False
    receives_order_mails: bool = False
    # The edit version the client read, checked when given; a row changed
    # since answers 409.
    expected_edit_version: int | None = None


# ── Results (outbound) ────────────────────────────────────────────────


class ContactOrganisationResult(ResultModel):
    kind: ContactOrganisationKind
    id: int
    name: str
    archived: bool


class ContactSummaryResult(ResultBase):
    """What another record shows of a contact it links to."""

    name: str
    role: str | None
    email: str | None
    phone: str | None
    mobile: str | None
    archived: bool
    anonymised: bool
    organisation: ContactOrganisationResult | None


class ContactResult(ResultBase):
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
    organisation: ContactOrganisationResult | None
    receives_request_mails: bool
    receives_order_mails: bool
    creator_id: int
    creator: PublicUserResult | None
    changed_by_id: int | None
    changed_by: PublicUserResult | None
    edit_version: int = 0


class PaginatedContacts:
    def __init__(self, total: int, items: list[ContactResult]):
        self.total = total
        self.items = items


class SupplierMailRecipientResult(ResultModel):
    contact_id: int
    name: str
    email: str


class SupplierMailRecipientsResult(ResultModel):
    """The contacts a supplier's request mails and order mails go to. An
    empty list means no contact is flagged, and the supplier's own address
    for that kind of mail applies."""

    supplier_id: int
    request: list[SupplierMailRecipientResult]
    order: list[SupplierMailRecipientResult]
