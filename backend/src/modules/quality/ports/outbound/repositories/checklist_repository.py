"""
Repository interface for the Checklist aggregate.
"""

from dataclasses import dataclass
from typing import Protocol
from typing import runtime_checkable
from uuid import UUID

from src.modules.quality.domain.entities.checklist import Checklist


@dataclass
class ChecklistFilterDto:
    skip: int | None = None
    limit: int | None = None
    project_id: int | None = None
    product_id: int | None = None
    # Checklists of this product and of the projects built on it.
    related_product_id: int | None = None
    creator_id: int | None = None
    # Only checklists of this owner kind: "personal", "project" or "product".
    owner: str | None = None
    type: str | None = None
    verdict: str | None = None
    # True for released checklists only, False for unreleased ones only.
    released: bool | None = None
    # Case-insensitive substring of the title or the document number.
    search: str | None = None
    # Only the latest revision of each checklist.
    latest_only: bool = True
    lineage: UUID | None = None
    # Hides other users' personal checklists from everyone except this
    # user. None lifts the restriction, for holders of manage:checklists.
    visible_to_user_id: int | None = None
    # "number", "title", "type", "verdict", "created", "changed" or "released";
    # without one the most recently changed come first.
    order_by: str | None = None
    # "asc" or "desc"; ascending when only order_by is given.
    order_dir: str | None = None


@runtime_checkable
class IChecklistRepository(Protocol):
    async def get_by_id(self, id: int) -> Checklist | None: ...

    async def get_for_update(self, id: int) -> Checklist | None:
        """See IControlledDocumentRepository.get_for_update."""
        ...

    async def get_by_public_id(self, public_id: UUID) -> Checklist | None: ...

    async def get_multi(self, filters: ChecklistFilterDto) -> tuple[int, list[Checklist]]:
        """Paginated, in the requested order or newest change first."""
        ...

    async def get_lineage(self, lineage: UUID) -> list[Checklist]:
        """Every revision of one checklist, newest revision first."""
        ...

    async def next_document_number(self, template: str) -> str:
        """The next free document number for a numbering template."""
        ...

    async def save(self, item: Checklist) -> Checklist: ...
    async def delete(self, item: Checklist) -> None: ...
