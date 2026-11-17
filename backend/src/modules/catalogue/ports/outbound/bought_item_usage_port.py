"""
The rows of other modules that name a bought item, which a merge moves to
the item it keeps: the lots that draw it, its order lines, bought and raw
material demands, the allocations that substitute it, and the device
components, quote request lines, quoted alternatives and printer links that
name it. Catalogue owns this port and calls it in the order the methods are
listed, which is the lock order of the lifecycle writers; Planning &
fulfillment implements it.
"""

from typing import Protocol


class IBoughtItemUsages(Protocol):
    async def merge_lot_sources(self, source_id: int, target_id: int) -> None: ...

    async def merge_order_items(self, source_id: int, target_id: int) -> None: ...

    async def merge_demand_items(self, source_id: int, target_id: int) -> None: ...

    async def merge_source_demands(self, source_id: int, target_id: int) -> None: ...

    async def merge_substitutions(self, source_id: int, target_id: int) -> None: ...

    async def merge_references(self, source_id: int, target_id: int) -> None: ...
