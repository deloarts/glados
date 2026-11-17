"""
Sets a made item's material source from another module's work, such as
Planning & fulfillment's lot approval, which assigns the approved raw
material to the item. The write runs in the caller's transaction.
"""

from src.modules.catalogue.domain.entities.made_item import MadeItem
from src.modules.catalogue.ports.outbound.repositories.made_item_repository import (
    IMadeItemRepository,
)
from src.modules.platform.domain.entities.user import User
from src.shared_kernel.domain.services.changelog_service import append_changelog
from src.shared_kernel.domain.services.clock import now_utc


class MadeItemMaterialSources:
    def __init__(self, made_item_repo: IMadeItemRepository) -> None:
        self._items = made_item_repo

    async def get_by_id(self, made_item_id: int) -> MadeItem | None:
        return await self._items.get_by_id(made_item_id)

    async def assign_source_item(
        self, made_item: MadeItem, source_item_id: int, actor: User, note: str
    ) -> None:
        """Makes `source_item_id` the item's material source and records
        `note` in its changelog."""
        made_item.source_item_id = source_item_id
        made_item.changed = now_utc()
        made_item.changed_by_id = actor.id
        made_item.changes = append_changelog(made_item.changes, actor.full_name, note)
        await self._items.save(made_item)
