"""
Reorder the process steps of a made item into a new sequence.
"""

from src.modules.catalogue.application.dto.made_item_dto import MadeItemProcessResult
from src.modules.catalogue.application.dto.made_item_dto import ReorderMadeItemProcessesCommand
from src.modules.catalogue.application.mappers.made_item_mapper import MadeItemProcessMapper
from src.modules.catalogue.application.services.made_item_revision_gate import (
    assert_made_item_editable,
)
from src.modules.catalogue.domain.errors import MadeItemNotFoundError
from src.modules.catalogue.domain.errors import MadeItemProcessReorderMismatchError
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


class ReorderMadeItemProcesses:
    def __init__(
        self,
        made_item_repo: IMadeItemRepository,
        admin_settings_repo: ICatalogueSettingsRepository,
        *,
        uow: IUnitOfWork,
    ) -> None:
        self._items = made_item_repo
        self._admin_settings = admin_settings_repo
        self._uow = uow

    async def execute(
        self, actor: User, made_item_id: int, cmd: ReorderMadeItemProcessesCommand
    ) -> list[MadeItemProcessResult]:
        MadeItemCatalogueRules.assert_can_update(actor)

        item = found_or_raise(
            await self._items.get_by_id(made_item_id),
            MadeItemNotFoundError,
            f"Catalogue item #{made_item_id} not found.",
        )

        await assert_made_item_editable(item, self._items, self._admin_settings)

        current = await self._items.get_processes(made_item_id)
        current_ids = {p.id for p in current}
        given_ids = set(cmd.ordered_process_ids)
        if current_ids != given_ids or len(cmd.ordered_process_ids) != len(current):
            raise MadeItemProcessReorderMismatchError(
                f"Reorder list for made item #{made_item_id} must contain exactly its "
                f"current process step IDs {sorted(current_ids)}, got "
                f"{cmd.ordered_process_ids!r}."
            )

        reordered = await self._items.reorder_processes(made_item_id, cmd.ordered_process_ids)
        await self._uow.commit()
        log.info(f"Reordered process steps of made item #{made_item_id}.")
        return [MadeItemProcessMapper.to_result(p) for p in reordered]
