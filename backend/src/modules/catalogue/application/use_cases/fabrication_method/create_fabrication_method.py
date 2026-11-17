"""
Bespoke (not the shared labeled_entity_crud helper) because a fabrication
method carries fields the generic "labeled entity" shape (article groups,
...) doesn't have, among them requires_machine and default_for_assemblies,
which moves the default off the previous holder.
"""

from src.modules.catalogue.application.dto.fabrication_method_dto import (
    CreateFabricationMethodCommand,
)
from src.modules.catalogue.application.dto.fabrication_method_dto import FabricationMethodResult
from src.modules.catalogue.application.mappers.fabrication_method_mapper import (
    FabricationMethodMapper,
)
from src.modules.catalogue.application.services.labeled_entity_crud import checked_label
from src.modules.catalogue.application.services.labeled_entity_crud import shown_name
from src.modules.catalogue.application.use_cases.fabrication_method._assembly_default import (
    clear_assembly_default,
)
from src.modules.catalogue.application.use_cases.fabrication_method._spec import SPEC
from src.modules.catalogue.domain.entities.fabrication_method import FabricationMethod
from src.modules.catalogue.domain.errors import SupplierNotFoundError
from src.modules.catalogue.domain.services.fabrication_method_rules import FabricationMethodRules
from src.modules.catalogue.ports.outbound.repositories.fabrication_method_repository import (
    IFabricationMethodRepository,
)
from src.modules.catalogue.ports.outbound.repositories.supplier_repository import (
    ISupplierRepository,
)
from src.modules.platform.domain.entities.user import User
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.ports.outbound.platform_settings_repository import (
    IPlatformSettingsRepository,
)
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork
from src.shared_kernel.domain.services.changelog_service import append_changelog
from src.shared_kernel.domain.services.clock import now_utc


class CreateFabricationMethod:
    def __init__(
        self,
        fabrication_method_repo: IFabricationMethodRepository,
        supplier_repo: ISupplierRepository,
        *,
        settings: IPlatformSettingsRepository,
        uow: IUnitOfWork,
    ) -> None:
        self._fabrication_methods = fabrication_method_repo
        self._suppliers = supplier_repo
        self._uow = uow
        self._settings = settings

    async def execute(
        self, actor: User, cmd: CreateFabricationMethodCommand
    ) -> FabricationMethodResult:
        FabricationMethodRules.assert_can_create(actor)

        name, description = await checked_label(
            SPEC, self._fabrication_methods, self._settings, 0, cmd.name, cmd.description
        )

        if cmd.default_supplier_id is not None and not await self._suppliers.get_by_id(
            cmd.default_supplier_id
        ):
            raise SupplierNotFoundError(f"Supplier #{cmd.default_supplier_id} not found.")

        if cmd.default_for_assemblies:
            await clear_assembly_default(self._fabrication_methods, actor, keep_id=0)

        now = now_utc()
        entity = FabricationMethod(
            id=0,
            created=now,
            changed=now,
            changes=append_changelog([], actor.full_name, "Fabrication method created."),
            name=name,
            label_color=cmd.label_color,
            label_font_color=cmd.label_font_color,
            description=description,
            creator_id=actor.id,
            creator=actor,
            requires_machine=cmd.requires_machine,
            required_external=cmd.required_external,
            default_supplier_id=cmd.default_supplier_id,
            lead_time_days=cmd.lead_time_days,
            default_for_assemblies=cmd.default_for_assemblies,
            sort_order=await self._fabrication_methods.next_sort_order(),
        )
        saved = await self._fabrication_methods.save(entity)
        await self._uow.commit()
        log.info(f"Created fabrication method {shown_name(saved.name)!r}, ID={saved.id}.")
        return FabricationMethodMapper.to_result(saved)
