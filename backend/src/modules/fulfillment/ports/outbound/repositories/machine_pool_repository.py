"""
Repository interface for the MachinePool catalogue aggregate.
"""

from dataclasses import dataclass
from typing import Protocol
from typing import runtime_checkable

from src.modules.fulfillment.domain.entities.machine_pool import MachinePool
from src.shared_kernel.domain.services.list_order import ListEntry


@dataclass
class MachinePoolFilterDto:
    skip: int | None = None
    limit: int | None = None
    search: str | None = None
    id: int | None = None
    name: str | None = None
    machine_id: int | None = None
    creator_id: int | None = None
    changed_by_id: int | None = None
    include_archived: bool = False
    order_by: str | None = None
    order_dir: str | None = None


@runtime_checkable
class IMachinePoolRepository(Protocol):
    async def get_by_id(self, id: int) -> MachinePool | None:
        """Regardless of `archived`, references must resolve."""
        ...

    async def get_by_ids(self, ids: list[int]) -> list[MachinePool]:
        """Batched get_by_id, also regardless of `archived`. Ids that do
        not resolve are simply absent from the result."""
        ...

    async def get_multi(self, filters: MachinePoolFilterDto) -> tuple[int, list[MachinePool]]: ...
    async def get_all(self) -> list[MachinePool]:
        """Unpaginated: every non-archived pool, no skip/limit/total.
        See IProductionMachineRepository.get_all's docstring; same reason,
        same scheduling-hot-path callers (auto-plan, schedule board).
        Ordered by the hand-kept `sort_order`."""
        ...

    async def get_list_order(self) -> list[ListEntry]:
        """Every pool's place in the hand-kept order, archived ones
        included."""
        ...

    async def next_sort_order(self) -> int:
        """The place after the last pool, where a new one goes."""
        ...

    async def set_sort_orders(self, sort_orders: dict[int, int]) -> None:
        """Writes the `sort_order` of each pool by id and nothing else."""
        ...

    async def save(self, item: MachinePool) -> MachinePool: ...
    async def delete(self, item: MachinePool) -> None: ...
