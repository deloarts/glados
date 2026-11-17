"""
A contact: a person of a customer or a supplier, or someone independent
such as an inspector, with the ways to reach them. Contacts are personal
data, so reading them needs read:contacts.
"""

from dataclasses import dataclass
from datetime import datetime

from src.modules.catalogue.domain.value_objects.contact_organisation_kind import (
    ContactOrganisationKind,
)
from src.modules.platform.domain.entities.user import User
from src.shared_kernel.domain.entities.base import Entity


@dataclass
class Contact(Entity):
    # ── Server-managed ────────────────────────────────────────────────
    created: datetime
    changed: datetime | None
    archived: bool
    # Set once the personal data was removed; the row stays so that what
    # links to it keeps resolving.
    anonymised_at: datetime | None

    # ── Person ────────────────────────────────────────────────────────
    name: str
    role: str | None
    email: str | None
    phone: str | None
    mobile: str | None
    note: str | None

    # ── Organisation, at most one of the two ──────────────────────────
    customer_id: int | None
    supplier_id: int | None

    # ── Supplier mails, only on a supplier's contact ──────────────────
    receives_request_mails: bool
    receives_order_mails: bool

    # ── Audit ─────────────────────────────────────────────────────────
    creator_id: int

    # ── Denormalized (read-only, populated by repository mapper) ──────
    organisation_name: str | None = None
    organisation_archived: bool = False
    creator: User | None = None
    changed_by_id: int | None = None
    changed_by: User | None = None

    # Moves on every change of the row, so an edit form can send the version
    # it read and learn of a concurrent edit.
    edit_version: int = 0

    @property
    def organisation_kind(self) -> ContactOrganisationKind | None:
        if self.customer_id is not None:
            return ContactOrganisationKind.CUSTOMER
        if self.supplier_id is not None:
            return ContactOrganisationKind.SUPPLIER
        return None

    @property
    def anonymised(self) -> bool:
        return self.anonymised_at is not None
