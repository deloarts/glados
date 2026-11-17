"""
Persistence ports for the hand-maintained lists product devices pick from.
The lists are short, so they are read whole rather than paged.
"""

from typing import Protocol
from typing import runtime_checkable

from src.modules.workspace.domain.entities.product_device_kind import ProductDeviceKind
from src.modules.workspace.domain.entities.product_device_option import ProductDeviceOption
from src.modules.workspace.domain.value_objects.product_device_option_category import (
    ProductDeviceOptionCategory,
)


@runtime_checkable
class IProductDeviceOptionRepository(Protocol):
    async def get_by_id(self, id: int) -> ProductDeviceOption | None:
        """Regardless of `archived`, references must resolve."""
        ...

    async def get_by_letter(self, letter: str) -> ProductDeviceOption | None:
        """Any driving medium with this letter, archived ones included,
        since letters stay unique across all rows."""
        ...

    async def get_many(
        self, category: ProductDeviceOptionCategory | None, include_archived: bool
    ) -> list[ProductDeviceOption]:
        """Ordered by category, `sort_order`, then id."""
        ...

    async def next_sort_order(self, category: ProductDeviceOptionCategory) -> int: ...

    async def save(self, option: ProductDeviceOption) -> ProductDeviceOption:
        """Insert (id == 0) or update (id > 0)."""
        ...

    async def set_sort_orders(self, sort_orders: dict[int, int]) -> None:
        """Writes the `sort_order` of each entry by id and nothing else."""
        ...


@runtime_checkable
class IProductDeviceKindRepository(Protocol):
    async def get_by_id(self, id: int) -> ProductDeviceKind | None:
        """With all positions and parameters, archived ones included."""
        ...

    async def get_many(self, include_archived: bool) -> list[ProductDeviceKind]:
        """Ordered by `sort_order`, then id, with their children."""
        ...

    async def next_sort_order(self) -> int: ...

    async def save(self, kind: ProductDeviceKind) -> ProductDeviceKind:
        """Insert or update the kind together with its positions and
        parameters: children with id 0 are inserted, the others updated.
        Children are never deleted."""
        ...

    async def set_sort_orders(self, sort_orders: dict[int, int]) -> None:
        """Writes the `sort_order` of each kind by id and nothing else."""
        ...
