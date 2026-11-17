"""
Creates a fabrication or inspection process step for a made item, validating
the chosen method, inheriting its default estimates, and assigning the step
to its group.
"""

from src.modules.catalogue.application.dto.made_item_dto import CreateMadeItemProcessCommand
from src.modules.catalogue.application.dto.made_item_dto import MadeItemProcessResult
from src.modules.catalogue.application.mappers.made_item_mapper import MadeItemProcessMapper
from src.modules.catalogue.application.services.made_item_revision_gate import (
    assert_made_item_editable,
)
from src.modules.catalogue.domain.entities.made_item_process import MadeItemProcess
from src.modules.catalogue.domain.errors import FabricationMethodArchivedError
from src.modules.catalogue.domain.errors import FabricationMethodNotFoundError
from src.modules.catalogue.domain.errors import InspectionMethodArchivedError
from src.modules.catalogue.domain.errors import InspectionMethodNotFoundError
from src.modules.catalogue.domain.errors import MadeItemNotFoundError
from src.modules.catalogue.domain.policies.inspection_method_rules import seed_inspection_estimates
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
from src.shared_kernel.domain.services.clock import now_utc


class CreateMadeItemProcess:
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
        self, actor: User, made_item_id: int, cmd: CreateMadeItemProcessCommand
    ) -> MadeItemProcessResult:
        MadeItemCatalogueRules.assert_can_update(actor)

        item = found_or_raise(
            await self._items.get_by_id(made_item_id),
            MadeItemNotFoundError,
            f"Catalogue item #{made_item_id} not found.",
        )

        await assert_made_item_editable(item, self._items, self._admin_settings)
        assert_valid_step_role(cmd.role, cmd.fabrication_method_id, cmd.inspection_method_id)

        setup_minutes = cmd.estimated_setup_minutes
        minutes_per_piece = cmd.estimated_minutes_per_piece
        if cmd.role == StepRole.FABRICATION:
            assert cmd.fabrication_method_id is not None  # guaranteed by assert_valid_step_role
            method = await self._fabrication_methods.get_by_id(cmd.fabrication_method_id)
            if not method:
                raise FabricationMethodNotFoundError(
                    f"Fabrication method #{cmd.fabrication_method_id} not found."
                )
            if method.archived:
                raise FabricationMethodArchivedError(
                    f"Fabrication method #{cmd.fabrication_method_id} is archived."
                )
        else:
            assert cmd.inspection_method_id is not None  # guaranteed by assert_valid_step_role
            inspection_method = await self._inspection_methods.get_by_id(cmd.inspection_method_id)
            if not inspection_method:
                raise InspectionMethodNotFoundError(
                    f"Inspection method #{cmd.inspection_method_id} not found."
                )
            if inspection_method.archived:
                raise InspectionMethodArchivedError(
                    f"Inspection method #{cmd.inspection_method_id} is archived."
                )
            # An inspection process inherits its method's default durations
            # unless the caller sent its own; every lot built from this
            # routing then copies them onto its step.
            setup_minutes, minutes_per_piece = seed_inspection_estimates(
                inspection_method, setup_minutes, minutes_per_piece
            )

        existing = await self._items.get_processes(made_item_id)
        # A process added via this single-step endpoint always becomes its
        # own new group, ignoring any group_index on the request, grouping
        # existing steps together is only ever done via the regroup endpoint.
        next_group_index = max((p.group_index for p in existing), default=-1) + 1
        process = MadeItemProcess(
            id=0,
            created=now_utc(),
            note=cmd.note,
            estimated_setup_minutes=setup_minutes,
            estimated_minutes_per_piece=minutes_per_piece,
            creator_id=actor.id,
            fabrication_method_id=cmd.fabrication_method_id,
            made_item_id=made_item_id,
            position=len(existing),
            group_index=next_group_index,
            role=cmd.role,
            inspection_method_id=cmd.inspection_method_id,
        )

        saved = await self._items.save_process(process)
        await self._uow.commit()
        log.info(f"Added process step #{saved.id} to made item #{made_item_id}.")
        return MadeItemProcessMapper.to_result(saved)
