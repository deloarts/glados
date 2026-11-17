"""
Abstract interface for inspection method persistence.
The application layer depends on this, never on the SQLAlchemy implementation.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from typing import runtime_checkable

from src.modules.catalogue.domain.entities.inspection_method import InspectionMethod
from src.modules.catalogue.ports.outbound.repositories.labeled_catalogue_filter import (
    LabeledCatalogueFilterDto,
)
from src.modules.platform.domain.value_objects.localized_text import LocalizedText
from src.shared_kernel.domain.services.list_order import ListEntry


@dataclass
class InspectionMethodFilterDto(LabeledCatalogueFilterDto):
    """The list filter for inspection methods."""


@runtime_checkable
class IInspectionMethodRepository(Protocol):
    async def get_by_id(self, id: int) -> InspectionMethod | None:
        """Regardless of `archived`, references must resolve."""
        ...

    async def get_live_names(self) -> list[tuple[int, LocalizedText]]:
        """The id and name of every live (not archived) row, for the
        per-language name uniqueness check."""
        ...

    async def get_multi(
        self, filters: InspectionMethodFilterDto
    ) -> tuple[int, list[InspectionMethod]]: ...

    async def get_aggregate(self) -> tuple[int, datetime | None]:
        """(row count, max(changed)) over every row, archived rows included. It
        is a cheap aggregate for the ETag of GET /pat/lookups and loads no row."""
        ...

    async def save(self, inspection_method: InspectionMethod) -> InspectionMethod:
        """Insert (id == 0) or update (id > 0)."""
        ...

    async def delete(self, inspection_method: InspectionMethod) -> None: ...

    async def get_list_order(self) -> list[ListEntry]:
        """Every row's place in the hand-kept order, archived rows included."""
        ...

    async def next_sort_order(self) -> int:
        """The place after the last row, where a new row goes."""
        ...

    async def set_sort_orders(self, sort_orders: dict[int, int]) -> None:
        """Writes the `sort_order` of each row by id and nothing else."""
        ...
