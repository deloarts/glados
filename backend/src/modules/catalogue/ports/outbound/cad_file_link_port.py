"""
Which of an item's files the CAD source manages, so the item file lists can
mark them. Catalogue owns this port; CAD & external data's PDM document link
repository answers it as it is.
"""

from typing import Protocol


class ICadFileLinks(Protocol):
    async def get_linked_item_file_ids(self, item_file_ids: list[int]) -> set[int]:
        """The ids among `item_file_ids` that a CAD document is linked to."""
        ...
