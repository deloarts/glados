"""
Deletes a made-item process step and re-sequences the remaining steps so no
gap is left in their position order.
"""

from src.modules.catalogue.application.services.made_item_revision_gate import (
    assert_made_item_editable,
)
from src.modules.catalogue.domain.errors import MadeItemNotFoundError
from src.modules.catalogue.domain.errors import MadeItemProcessNotFoundError
from src.modules.catalogue.domain.policies.made_item_rules import MadeItemCatalogueRules
from src.modules.catalogue.ports.outbound.catalogue_settings_repository import (
    ICatalogueSettingsRepository,
)
from src.modules.catalogue.ports.outbound.repositories.made_item_repository import (
    IMadeItemRepository,
)
from src.modules.platform.application.services.lookup import found_or_raise
from src.modules.platform.domain.entities.user import User
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork


class DeleteMadeItemProcess:
    def __init__(
        self,
        made_item_repo: IMadeItemRepository,
        admin_settings_repo: ICatalogueSettingsRepository,
        uow: IUnitOfWork,
    ) -> None:
        self._items = made_item_repo
        self._admin_settings = admin_settings_repo
        self._uow = uow

    async def execute(self, actor: User, item_id: int, process_id: int) -> None:
        process = await self._items.get_process_by_id(process_id)
        if not process or process.made_item_id != item_id:
            # A process id that exists but belongs to another made item
            # 404s, matching the sibling reorder/regroup routes on the
            # same file, which already scope to made_item_id.
            raise MadeItemProcessNotFoundError(f"Process step #{process_id} not found.")

        MadeItemCatalogueRules.assert_can_update(actor)
        item = found_or_raise(
            await self._items.get_by_id(item_id),
            MadeItemNotFoundError,
            f"Catalogue item #{item_id} not found.",
        )
        await assert_made_item_editable(item, self._items, self._admin_settings)

        made_item_id = process.made_item_id
        await self._items.delete_process(process)

        # Re-sequence remaining steps to close the position gap left by the delete.
        remaining_ids = [p.id for p in await self._items.get_processes(made_item_id)]
        if remaining_ids:
            await self._items.reorder_processes(made_item_id, remaining_ids)
        await self._uow.commit()

        log.info(f"Deleted process step #{process_id}.")
