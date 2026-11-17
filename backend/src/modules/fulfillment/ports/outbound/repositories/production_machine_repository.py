"""
Repository interface for the ProductionMachine catalogue aggregate.
"""

from dataclasses import dataclass
from typing import Protocol
from typing import runtime_checkable

from src.modules.fulfillment.domain.entities.production_machine import ProductionMachine
from src.shared_kernel.domain.services.list_order import ListEntry


@dataclass
class ProductionMachineFilterDto:
    skip: int | None = None
    limit: int | None = None
    search: str | None = None
    id: int | None = None
    internal_name: str | None = None
    vendor: str | None = None
    model: str | None = None
    fabrication_method_id: int | None = None
    creator_id: int | None = None
    changed_by_id: int | None = None
    include_archived: bool = False
    order_by: str | None = None
    order_dir: str | None = None


@runtime_checkable
class IProductionMachineRepository(Protocol):
    async def get_by_id(self, id: int) -> ProductionMachine | None:
        """Regardless of `archived`, references must resolve."""
        ...

    async def get_by_ids(self, ids: list[int]) -> list[ProductionMachine]:
        """Batched get_by_id, also regardless of `archived`. Ids that do
        not resolve are simply absent from the result."""
        ...

    async def get_multi(
        self, filters: ProductionMachineFilterDto
    ) -> tuple[int, list[ProductionMachine]]: ...
    async def get_all(self) -> list[ProductionMachine]:
        """Unpaginated: every non-archived machine, no skip/limit/
        total. Scheduling hot paths (auto-plan, schedule board) need the
        *entire* active roster to consider every machine, not a UI page
        of it; `get_multi(FilterDto())` silently clamps to
        `DEFAULT_PAGE_SIZE` (pagination.py) past the 100th machine.
        `get_multi` stays exactly as-is for genuinely paginated callers
        (production_machine/get_machine.py). Ordered by the hand-kept
        `sort_order`, so the schedule board lists the machines that way."""
        ...

    async def get_list_order(self) -> list[ListEntry]:
        """Every machine's place in the hand-kept order, archived ones
        included."""
        ...

    async def next_sort_order(self) -> int:
        """The place after the last machine, where a new one goes."""
        ...

    async def set_sort_orders(self, sort_orders: dict[int, int]) -> None:
        """Writes the `sort_order` of each machine by id and nothing else."""
        ...

    async def save(self, item: ProductionMachine) -> ProductionMachine: ...
    async def delete(self, item: ProductionMachine) -> None: ...
