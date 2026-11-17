"""
Creates a new source item type using the shared labeled-entity CRUD
logic.
"""

from src.modules.catalogue.application.dto.source_item_type_dto import CreateSourceItemTypeCommand
from src.modules.catalogue.application.dto.source_item_type_dto import SourceItemTypeResult
from src.modules.catalogue.application.mappers.source_item_type_mapper import SourceItemTypeMapper
from src.modules.catalogue.application.services.labeled_entity_crud import create_labeled_entity
from src.modules.catalogue.application.use_cases.source_item_type._spec import SPEC
from src.modules.catalogue.ports.outbound.repositories.source_item_type_repository import (
    ISourceItemTypeRepository,
)
from src.modules.platform.domain.entities.user import User
from src.modules.platform.ports.outbound.platform_settings_repository import (
    IPlatformSettingsRepository,
)
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork


class CreateSourceItemType:
    def __init__(
        self,
        source_item_type_repo: ISourceItemTypeRepository,
        *,
        settings: IPlatformSettingsRepository,
        uow: IUnitOfWork,
    ) -> None:
        self._source_item_types = source_item_type_repo
        self._settings = settings
        self._uow = uow

    async def execute(self, actor: User, cmd: CreateSourceItemTypeCommand) -> SourceItemTypeResult:
        saved = await create_labeled_entity(
            SPEC, self._source_item_types, self._settings, actor, cmd
        )
        await self._uow.commit()
        return SourceItemTypeMapper.to_result(saved)
