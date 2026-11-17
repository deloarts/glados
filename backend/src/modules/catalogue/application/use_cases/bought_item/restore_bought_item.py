"""
Restores an archived catalogue item. Raises BoughtItemGtinDuplicateError
(409) if another live item already holds this one's GTIN (the live-row
uniqueness `uq_bought_item_gtin_active` would otherwise be violated).
`part_number` is never checked here: its uniqueness is TOTAL (see
bought_item_model.py), archived rows included, so restoring can never
violate it. Idempotent: restoring an already-live item is not an error.
"""

from src.modules.catalogue.application.dto.bought_item_dto import BoughtItemResult
from src.modules.catalogue.application.mappers.bought_item_mapper import BoughtItemMapper
from src.modules.catalogue.domain.entities.bought_item import BoughtItem
from src.modules.catalogue.domain.errors import BoughtItemGtinDuplicateError
from src.modules.catalogue.domain.errors import BoughtItemNotFoundError
from src.modules.catalogue.domain.policies.bought_item_rules import BoughtItemCatalogueRules
from src.modules.catalogue.ports.outbound.repositories.bought_item_repository import (
    IBoughtItemRepository,
)
from src.modules.platform.application.services.archive_restore import set_archived
from src.modules.platform.domain.entities.user import User
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork
from src.shared_kernel.domain.services.changelog_service import append_changelog
from src.shared_kernel.domain.services.clock import now_utc


class RestoreBoughtItem:
    def __init__(
        self,
        bought_item_repo: IBoughtItemRepository,
        *,
        uow: IUnitOfWork,
    ) -> None:
        self._items = bought_item_repo
        self._uow = uow

    async def execute(self, actor: User, item_id: int) -> BoughtItemResult:
        BoughtItemCatalogueRules.assert_can_restore(actor)

        async def _before_save(item: BoughtItem) -> None:
            if item.archived and item.gtin:
                conflict = await self._items.get_by_gtin(item.gtin)
                if conflict and conflict.id != item.id:
                    raise BoughtItemGtinDuplicateError(f"GTIN {item.gtin!r} is already in use.")

            item.changed = now_utc()
            item.changes = append_changelog(
                item.changes, actor.full_name, "Catalogue item restored."
            )

        saved = await set_archived(
            entity_id=item_id,
            archived=False,
            load=self._items.get_by_id,
            not_found=lambda iid: BoughtItemNotFoundError(f"Catalogue item #{iid} not found."),
            save=self._items.save,
            before_save=_before_save,
        )
        await self._uow.commit()
        log.info(f"Restored catalogue item {saved.article_name!r}, ID={saved.id}.")
        return BoughtItemMapper.to_result(saved)
