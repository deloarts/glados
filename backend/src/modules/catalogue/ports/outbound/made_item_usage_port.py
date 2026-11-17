"""
The rows of other modules that name a made item, which a merge moves to the
item it keeps: the lots that make or draw it and its demands. Catalogue owns
this port and Planning & fulfillment implements it.
"""

from typing import Protocol


class IMadeItemUsages(Protocol):
    async def merge_lots_and_demands(self, source_id: int, target_id: int) -> None:
        """Moves the lots, then the demands, in the lifecycle lock order."""
        ...
