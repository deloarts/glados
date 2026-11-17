"""
Reorder and regroup process steps of a made item into logical groups.
"""

from src.modules.catalogue.application.dto.made_item_dto import MadeItemProcessResult
from src.modules.catalogue.application.dto.made_item_dto import RegroupMadeItemProcessesCommand
from src.modules.catalogue.application.mappers.made_item_mapper import MadeItemProcessMapper
from src.modules.catalogue.application.services.made_item_revision_gate import (
    assert_made_item_editable,
)
from src.modules.catalogue.domain.errors import MadeItemNotFoundError
from src.modules.catalogue.domain.policies.made_item_rules import MadeItemCatalogueRules
from src.modules.catalogue.domain.policies.made_item_rules import validate_process_grouping
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


class RegroupMadeItemProcesses:
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
        self, actor: User, made_item_id: int, cmd: RegroupMadeItemProcessesCommand
    ) -> list[MadeItemProcessResult]:
        MadeItemCatalogueRules.assert_can_update(actor)

        item = found_or_raise(
            await self._items.get_by_id(made_item_id),
            MadeItemNotFoundError,
            f"Catalogue item #{made_item_id} not found.",
        )

        await assert_made_item_editable(item, self._items, self._admin_settings)

        processes = await self._items.get_processes(made_item_id)
        validate_process_grouping(processes, cmd.groups)

        regrouped = await self._items.set_process_groups(made_item_id, cmd.groups)
        await self._uow.commit()
        log.info(f"Regrouped process steps of made item #{made_item_id}.")
        return [MadeItemProcessMapper.to_result(p) for p in regrouped]
