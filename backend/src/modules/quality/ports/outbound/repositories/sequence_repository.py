"""
Repository interface for the Sequence aggregate.
"""

from dataclasses import dataclass
from typing import Protocol
from typing import runtime_checkable
from uuid import UUID

from src.modules.quality.domain.entities.sequence import Sequence


@dataclass
class SequenceFilterDto:
    skip: int | None = None
    limit: int | None = None
    product_id: int | None = None
    creator_id: int | None = None
    # True for released sequences only, False for drafts only.
    released: bool | None = None
    # Case-insensitive substring of the name or the document number.
    search: str | None = None
    # Only the latest revision of each sequence.
    latest_only: bool = True
    lineage: UUID | None = None
    # "number", "title", "created", "changed" or "released"; without one the
    # most recently changed come first. "title" sorts by the name.
    order_by: str | None = None
    # "asc" or "desc"; ascending when only order_by is given.
    order_dir: str | None = None
    # The shared document filter fields a sequence has no use for: it
    # always belongs to a product and is visible to everyone.
    project_id: None = None
    related_product_id: None = None
    owner: None = None
    visible_to_user_id: None = None


@runtime_checkable
class ISequenceRepository(Protocol):
    async def get_by_id(self, id: int) -> Sequence | None: ...

    async def get_for_update(self, id: int) -> Sequence | None:
        """See IControlledDocumentRepository.get_for_update."""
        ...

    async def get_by_public_id(self, public_id: UUID) -> Sequence | None: ...

    async def get_multi(self, filters: SequenceFilterDto) -> tuple[int, list[Sequence]]:
        """Paginated, newest change first."""
        ...

    async def get_lineage(self, lineage: UUID) -> list[Sequence]:
        """Every revision of one sequence, newest revision first."""
        ...

    async def next_document_number(self, template: str) -> str:
        """The next free document number for a numbering template."""
        ...

    async def save(self, item: Sequence) -> Sequence: ...

    async def delete(self, item: Sequence) -> None: ...
