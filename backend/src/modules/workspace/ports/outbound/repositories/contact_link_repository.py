"""
Repository interface for the contact links of products and projects.
"""

from dataclasses import dataclass
from typing import Protocol
from typing import runtime_checkable

from src.modules.workspace.domain.entities.contact_link import ContactLink
from src.modules.workspace.domain.value_objects.contact_link_owner import ContactLinkOwner


@dataclass(frozen=True)
class ContactUsageRow:
    """One live product or project that links a contact."""

    contact_id: int
    owner: ContactLinkOwner
    owner_id: int
    number: str
    receives_meeting_notes: bool


@runtime_checkable
class IContactLinkRepository(Protocol):
    async def get_links(self, owner: ContactLinkOwner, owner_id: int) -> list[ContactLink]:
        """The links of one product or project, oldest first."""
        ...

    async def get_link(
        self, owner: ContactLinkOwner, owner_id: int, contact_id: int
    ) -> ContactLink | None: ...

    async def save(self, link: ContactLink) -> ContactLink: ...

    async def delete(self, link: ContactLink) -> None: ...

    async def get_usage(self, contact_ids: list[int]) -> list[ContactUsageRow]:
        """The live products and the projects not deleted that link any of
        the contacts, by number."""
        ...
