"""
Update a single process step: fabrication or inspection method, notes,
and time estimates.
"""

from src.modules.catalogue.application.dto.made_item_dto import MadeItemProcessResult
from src.modules.catalogue.application.dto.made_item_dto import UpdateMadeItemProcessCommand
from src.modules.catalogue.application.mappers.made_item_mapper import MadeItemProcessMapper
from src.modules.catalogue.application.services.made_item_revision_gate import (
    assert_made_item_editable,
)
from src.modules.catalogue.domain.errors import FabricationMethodArchivedError
from src.modules.catalogue.domain.errors import FabricationMethodNotFoundError
from src.modules.catalogue.domain.errors import InspectionMethodArchivedError
from src.modules.catalogue.domain.errors import InspectionMethodNotFoundError
from src.modules.catalogue.domain.errors import MadeItemNotFoundError
from src.modules.catalogue.domain.errors import MadeItemProcessGroupingInvalidError
from src.modules.catalogue.domain.errors import MadeItemProcessNotFoundError
from src.modules.catalogue.domain.policies.made_item_rules import MadeItemCatalogueRules
from src.modules.catalogue.domain.policies.made_item_rules import assert_valid_step_role
from src.modules.catalogue.domain.value_objects.step_role import StepRole
from src.modules.catalogue.ports.outbound.catalogue_settings_repository import (
    ICatalogueSettingsRepository,
)
from src.modules.catalogue.ports.outbound.repositories.fabrication_method_repository import (
    IFabricationMethodRepository,
)
from src.modules.catalogue.ports.outbound.repositories.inspection_method_repository import (
    IInspectionMethodRepository,
)
from src.modules.catalogue.ports.outbound.repositories.made_item_repository import (
    IMadeItemRepository,
)
from src.modules.platform.application.services.lookup import found_or_raise
from src.modules.platform.domain.entities.user import User
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork


class UpdateMadeItemProcess:
    def __init__(
        self,
        made_item_repo: IMadeItemRepository,
        fabrication_method_repo: IFabricationMethodRepository,
        inspection_method_repo: IInspectionMethodRepository,
        admin_settings_repo: ICatalogueSettingsRepository,
        *,
        uow: IUnitOfWork,
    ) -> None:
        self._items = made_item_repo
        self._fabrication_methods = fabrication_method_repo
        self._inspection_methods = inspection_method_repo
        self._admin_settings = admin_settings_repo
        self._uow = uow

    async def execute(
        self, actor: User, item_id: int, process_id: int, cmd: UpdateMadeItemProcessCommand
    ) -> MadeItemProcessResult:
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
        assert_valid_step_role(cmd.role, cmd.fabrication_method_id, cmd.inspection_method_id)

        if cmd.role != process.role:
            raise MadeItemProcessGroupingInvalidError(
                f"Process step #{process_id}'s role cannot be changed from "
                f"{process.role.value!r} to {cmd.role.value!r}; delete and re-add instead."
            )

        if cmd.role == StepRole.FABRICATION:
            assert cmd.fabrication_method_id is not None  # guaranteed by assert_valid_step_role
            changing_method = cmd.fabrication_method_id != process.fabrication_method_id
            method = await self._fabrication_methods.get_by_id(cmd.fabrication_method_id)
            if not method:
                raise FabricationMethodNotFoundError(
                    f"Fabrication method #{cmd.fabrication_method_id} not found."
                )
            if changing_method and method.archived:
                raise FabricationMethodArchivedError(
                    f"Fabrication method #{cmd.fabrication_method_id} is archived."
                )
        else:
            assert cmd.inspection_method_id is not None  # guaranteed by assert_valid_step_role
            changing_method = cmd.inspection_method_id != process.inspection_method_id
            inspection_method = await self._inspection_methods.get_by_id(cmd.inspection_method_id)
            if not inspection_method:
                raise InspectionMethodNotFoundError(
                    f"Inspection method #{cmd.inspection_method_id} not found."
                )
            if changing_method and inspection_method.archived:
                raise InspectionMethodArchivedError(
                    f"Inspection method #{cmd.inspection_method_id} is archived."
                )

        process.fabrication_method_id = cmd.fabrication_method_id
        process.inspection_method_id = cmd.inspection_method_id
        process.note = cmd.note
        process.estimated_setup_minutes = cmd.estimated_setup_minutes
        process.estimated_minutes_per_piece = cmd.estimated_minutes_per_piece

        saved = await self._items.save_process(process)
        await self._uow.commit()
        log.info(f"Updated process step #{saved.id}.")
        return MadeItemProcessMapper.to_result(saved)
