"""
Abstract interface for contact persistence.
"""

from dataclasses import dataclass
from typing import Protocol

from src.modules.catalogue.domain.entities.contact import Contact


@dataclass
class ContactFilterDto:
    search: str | None = None
    name: str | None = None
    email: str | None = None
    phone: str | None = None
    # Narrows to one organisation, or by its kind: "customer", "supplier"
    # or "none" for the contacts that belong to neither.
    customer_id: int | None = None
    supplier_id: int | None = None
    organisation_kind: str | None = None
    include_archived: bool = False
    skip: int | None = None
    limit: int | None = None
    # "name", "organisation" (the organisation's name, then the contact's),
    # "created" or "changed".
    order_by: str | None = None
    order_dir: str | None = None


class IContactRepository(Protocol):
    async def get_by_id(self, id: int) -> Contact | None:
        """Regardless of `archived`, links must resolve."""
        ...

    async def get_by_ids(self, ids: list[int]) -> list[Contact]:
        """Archived rows included, in no particular order."""
        ...

    async def lock_for_update(self, id: int) -> None:
        """Locks the row until the transaction ends, so the edit version an
        edit checks is the one it overwrites."""
        ...

    async def get_multi(self, filters: ContactFilterDto) -> tuple[int, list[Contact]]: ...

    async def get_mail_recipients(self, supplier_id: int) -> list[Contact]:
        """The live contacts of a supplier with an e-mail address and at
        least one of the two mail flags, by name."""
        ...

    async def save(self, contact: Contact) -> Contact: ...
