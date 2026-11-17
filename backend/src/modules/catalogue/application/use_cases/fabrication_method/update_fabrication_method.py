"""
Bespoke (not the shared labeled_entity_crud helper), see
create_fabrication_method.py's docstring.
"""

from src.modules.catalogue.application.dto.fabrication_method_dto import FabricationMethodResult
from src.modules.catalogue.application.dto.fabrication_method_dto import (
    UpdateFabricationMethodCommand,
)
from src.modules.catalogue.application.mappers.fabrication_method_mapper import (
    FabricationMethodMapper,
)
from src.modules.catalogue.application.services.labeled_entity_crud import checked_label
from src.modules.catalogue.application.services.labeled_entity_crud import label_changelog
from src.modules.catalogue.application.services.labeled_entity_crud import shown_name
from src.modules.catalogue.application.use_cases.fabrication_method._assembly_default import (
    clear_assembly_default,
)
from src.modules.catalogue.application.use_cases.fabrication_method._spec import SPEC
from src.modules.catalogue.domain.errors import FabricationMethodNotFoundError
from src.modules.catalogue.domain.errors import SupplierNotFoundError
from src.modules.catalogue.domain.services.fabrication_method_rules import FabricationMethodRules
from src.modules.catalogue.ports.outbound.repositories.fabrication_method_repository import (
    IFabricationMethodRepository,
)
from src.modules.catalogue.ports.outbound.repositories.supplier_repository import (
    ISupplierRepository,
)
from src.modules.platform.application.services.schedule_recompute_port import ScheduleRecompute
from src.modules.platform.application.services.schedule_recompute_port import (
    recompute_schedule_after_commit,
)
from src.modules.platform.domain.entities.user import User
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.ports.outbound.platform_settings_repository import (
    IPlatformSettingsRepository,
)
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork
from src.shared_kernel.domain.services.changelog_service import append_changelog
from src.shared_kernel.domain.services.clock import now_utc


class UpdateFabricationMethod:
    def __init__(
        self,
        fabrication_method_repo: IFabricationMethodRepository,
        supplier_repo: ISupplierRepository,
        *,
        settings: IPlatformSettingsRepository,
        uow: IUnitOfWork,
        recompute_schedule: ScheduleRecompute | None = None,
    ) -> None:
        self._fabrication_methods = fabrication_method_repo
        self._suppliers = supplier_repo
        self._uow = uow
        self._settings = settings
        self._recompute = recompute_schedule

    async def execute(
        self,
        actor: User,
        fabrication_method_id: int,
        cmd: UpdateFabricationMethodCommand,
    ) -> FabricationMethodResult:
        FabricationMethodRules.assert_can_update(actor)

        entity = await self._fabrication_methods.get_by_id(fabrication_method_id)
        if not entity:
            raise FabricationMethodNotFoundError(
                f"Fabrication method #{fabrication_method_id} not found."
            )

        name, description = await checked_label(
            SPEC, self._fabrication_methods, self._settings, entity.id, cmd.name, cmd.description
        )

        if cmd.default_supplier_id is not None and not await self._suppliers.get_by_id(
            cmd.default_supplier_id
        ):
            raise SupplierNotFoundError(f"Supplier #{cmd.default_supplier_id} not found.")

        if cmd.default_for_assemblies:
            FabricationMethodRules.assert_can_be_assembly_default(entity)
            await clear_assembly_default(self._fabrication_methods, actor, keep_id=entity.id)

        changelog_entry = label_changelog(entity, cmd, name, description)

        entity.name = name
        entity.label_color = cmd.label_color
        entity.label_font_color = cmd.label_font_color
        entity.description = description
        entity.requires_machine = cmd.requires_machine
        entity.required_external = cmd.required_external
        entity.default_supplier_id = cmd.default_supplier_id
        entity.lead_time_days = cmd.lead_time_days
        entity.default_for_assemblies = cmd.default_for_assemblies
        entity.changed = now_utc()
        entity.changes = append_changelog(entity.changes, actor.full_name, changelog_entry)

        saved = await self._fabrication_methods.save(entity)
        await self._uow.commit()
        # Its lead time dates the external steps that use it.
        await recompute_schedule_after_commit(
            self._recompute, after="changing a fabrication method; the change itself is committed."
        )
        log.info(f"Updated fabrication method {shown_name(saved.name)!r}, ID={saved.id}.")
        return FabricationMethodMapper.to_result(saved)
