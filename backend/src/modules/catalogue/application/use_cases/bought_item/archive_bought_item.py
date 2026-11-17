"""
Archives a catalogue item and appends a changelog entry. Idempotent:
archiving an already-archived item is not an error.
"""

from src.modules.catalogue.application.dto.bought_item_dto import BoughtItemResult
from src.modules.catalogue.application.mappers.bought_item_mapper import BoughtItemMapper
from src.modules.catalogue.domain.entities.bought_item import BoughtItem
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


class ArchiveBoughtItem:
    def __init__(
        self,
        bought_item_repo: IBoughtItemRepository,
        *,
        uow: IUnitOfWork,
    ) -> None:
        self._items = bought_item_repo
        self._uow = uow

    async def execute(self, actor: User, item_id: int) -> BoughtItemResult:
        BoughtItemCatalogueRules.assert_can_archive(actor)

        async def _before_save(item: BoughtItem) -> None:
            item.changed = now_utc()
            item.changes = append_changelog(
                item.changes, actor.full_name, "Catalogue item archived."
            )

        saved = await set_archived(
            entity_id=item_id,
            archived=True,
            load=self._items.get_by_id,
            not_found=lambda iid: BoughtItemNotFoundError(f"Catalogue item #{iid} not found."),
            save=self._items.save,
            before_save=_before_save,
        )
        await self._uow.commit()
        log.info(f"Archived catalogue item {saved.article_name!r}, ID={saved.id}.")
        return BoughtItemMapper.to_result(saved)
