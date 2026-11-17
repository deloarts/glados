"""
Archives a made item by setting archived=true and recording the change in
its changelog. Idempotent: archiving an already-archived item is not an
error.
"""

from src.modules.catalogue.application.dto.made_item_dto import MadeItemResult
from src.modules.catalogue.application.mappers.made_item_mapper import MadeItemMapper
from src.modules.catalogue.domain.entities.made_item import MadeItem
from src.modules.catalogue.domain.errors import MadeItemNotFoundError
from src.modules.catalogue.domain.policies.made_item_rules import MadeItemCatalogueRules
from src.modules.catalogue.ports.outbound.repositories.made_item_repository import (
    IMadeItemRepository,
)
from src.modules.platform.application.services.archive_restore import set_archived
from src.modules.platform.domain.entities.user import User
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork
from src.shared_kernel.domain.services.changelog_service import append_changelog
from src.shared_kernel.domain.services.clock import now_utc


class ArchiveMadeItem:
    def __init__(
        self,
        made_item_repo: IMadeItemRepository,
        *,
        uow: IUnitOfWork,
    ) -> None:
        self._items = made_item_repo
        self._uow = uow

    async def execute(self, actor: User, item_id: int) -> MadeItemResult:
        MadeItemCatalogueRules.assert_can_archive(actor)

        async def _before_save(item: MadeItem) -> None:
            item.changed = now_utc()
            item.changes = append_changelog(
                item.changes, actor.full_name, "Catalogue item archived."
            )

        saved = await set_archived(
            entity_id=item_id,
            archived=True,
            load=self._items.get_by_id,
            not_found=lambda iid: MadeItemNotFoundError(f"Catalogue item #{iid} not found."),
            save=self._items.save,
            before_save=_before_save,
        )
        await self._uow.commit()
        log.info(f"Archived made-item catalogue item {saved.article_name!r}, ID={saved.id}.")
        return MadeItemMapper.to_result(saved)
