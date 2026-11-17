"""
Repository interface for the Calculation aggregate.
"""

from dataclasses import dataclass
from typing import Protocol
from typing import runtime_checkable
from uuid import UUID

from src.modules.quality.domain.entities.calculation import Calculation


@dataclass
class CalculationFilterDto:
    skip: int | None = None
    limit: int | None = None
    project_id: int | None = None
    product_id: int | None = None
    # Calculations of this product and of the projects built on it.
    related_product_id: int | None = None
    creator_id: int | None = None
    # Only calculations that refer to this product device.
    product_device_id: int | None = None
    # Only personal calculations (no project, no product).
    personal_only: bool = False
    # Only calculations of this owner kind: "personal", "project" or "product".
    owner: str | None = None
    # True for released calculations only, False for drafts only.
    released: bool | None = None
    tool: str | None = None
    # Case-insensitive substring of the title or the document number.
    search: str | None = None
    # Only the latest revision of each calculation.
    latest_only: bool = True
    lineage: UUID | None = None
    # Hides other users' personal calculations from everyone except this
    # user. None lifts the restriction, for holders of manage:calculations.
    visible_to_user_id: int | None = None
    # "number", "title", "tool", "created", "changed" or "released"; without one the
    # most recently changed come first.
    order_by: str | None = None
    # "asc" or "desc"; ascending when only order_by is given.
    order_dir: str | None = None


@runtime_checkable
class ICalculationRepository(Protocol):
    async def get_by_id(self, id: int) -> Calculation | None: ...

    async def get_for_update(self, id: int) -> Calculation | None:
        """See IControlledDocumentRepository.get_for_update."""
        ...

    async def get_by_public_id(self, public_id: UUID) -> Calculation | None: ...

    async def get_multi(self, filters: CalculationFilterDto) -> tuple[int, list[Calculation]]:
        """Paginated, newest change first."""
        ...

    async def get_lineage(self, lineage: UUID) -> list[Calculation]:
        """Every revision of one calculation, newest revision first."""
        ...

    async def next_document_number(self, template: str) -> str:
        """The next free document number for a numbering template."""
        ...

    async def save(self, item: Calculation) -> Calculation: ...
    async def delete(self, item: Calculation) -> None: ...
