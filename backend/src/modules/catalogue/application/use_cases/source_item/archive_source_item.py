"""
Idempotent: archiving an already-archived source item is not an error.
"""

from src.modules.catalogue.application.dto.source_item_dto import SourceItemResult
from src.modules.catalogue.application.mappers.source_item_mapper import SourceItemMapper
from src.modules.catalogue.domain.entities.source_item import SourceItem
from src.modules.catalogue.domain.errors import SourceItemNotFoundError
from src.modules.catalogue.domain.policies.source_item_rules import SourceItemCatalogueRules
from src.modules.catalogue.ports.outbound.repositories.source_item_repository import (
    ISourceItemRepository,
)
from src.modules.platform.application.services.archive_restore import set_archived
from src.modules.platform.domain.entities.user import User
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork
from src.shared_kernel.domain.services.changelog_service import append_changelog
from src.shared_kernel.domain.services.clock import now_utc


class ArchiveSourceItem:
    def __init__(
        self,
        source_item_repo: ISourceItemRepository,
        *,
        uow: IUnitOfWork,
    ) -> None:
        self._items = source_item_repo
        self._uow = uow

    async def execute(self, actor: User, item_id: int) -> SourceItemResult:
        SourceItemCatalogueRules.assert_can_archive(actor)

        async def _before_save(item: SourceItem) -> None:
            item.changed = now_utc()
            item.changes = append_changelog(item.changes, actor.full_name, "Source item archived.")

        saved = await set_archived(
            entity_id=item_id,
            archived=True,
            load=self._items.get_by_id,
            not_found=lambda iid: SourceItemNotFoundError(f"Source item #{iid} not found."),
            save=self._items.save,
            before_save=_before_save,
        )
        await self._uow.commit()
        log.info(f"Archived source item #{saved.id}.")
        return SourceItemMapper.to_result(saved)
