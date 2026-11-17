"""
Bespoke (not the shared labeled_entity_crud helper) because
requires_evidence is an inspection-method-only field the generic
"labeled entity" shape (article groups, ...) doesn't have.
"""

from src.modules.catalogue.application.dto.inspection_method_dto import (
    CreateInspectionMethodCommand,
)
from src.modules.catalogue.application.dto.inspection_method_dto import InspectionMethodResult
from src.modules.catalogue.application.mappers.inspection_method_mapper import (
    InspectionMethodMapper,
)
from src.modules.catalogue.application.services.labeled_entity_crud import checked_label
from src.modules.catalogue.application.services.labeled_entity_crud import shown_name
from src.modules.catalogue.application.use_cases.inspection_method._spec import SPEC
from src.modules.catalogue.domain.entities.inspection_method import InspectionMethod
from src.modules.catalogue.domain.errors import MachineCapabilityMismatchError
from src.modules.catalogue.domain.errors import ProductionMachineNotFoundError
from src.modules.catalogue.domain.policies.inspection_method_rules import InspectionMethodRules
from src.modules.catalogue.ports.outbound.default_machine_port import IDefaultMachineLookup
from src.modules.catalogue.ports.outbound.repositories.inspection_method_repository import (
    IInspectionMethodRepository,
)
from src.modules.platform.domain.entities.user import User
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.ports.outbound.platform_settings_repository import (
    IPlatformSettingsRepository,
)
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork
from src.shared_kernel.domain.services.changelog_service import append_changelog
from src.shared_kernel.domain.services.clock import now_utc


class CreateInspectionMethod:
    def __init__(
        self,
        inspection_method_repo: IInspectionMethodRepository,
        machine_repo: IDefaultMachineLookup,
        *,
        settings: IPlatformSettingsRepository,
        uow: IUnitOfWork,
    ) -> None:
        self._inspection_methods = inspection_method_repo
        self._machines = machine_repo
        self._uow = uow
        self._settings = settings

    async def execute(
        self, actor: User, cmd: CreateInspectionMethodCommand
    ) -> InspectionMethodResult:
        InspectionMethodRules.assert_can_create(actor)

        name, description = await checked_label(
            SPEC, self._inspection_methods, self._settings, 0, cmd.name, cmd.description
        )

        if cmd.default_machine_id is not None:
            machine = await self._machines.get_by_id(cmd.default_machine_id)
            if not machine:
                raise ProductionMachineNotFoundError(
                    f"Machine #{cmd.default_machine_id} not found."
                )
            if not machine.is_qa_machine:
                raise MachineCapabilityMismatchError(
                    f"Machine #{machine.id} ({machine.internal_name}) is not a QA/measuring "
                    f"machine and cannot be an inspection method's default machine."
                )

        now = now_utc()
        entity = InspectionMethod(
            id=0,
            created=now,
            changed=now,
            changes=append_changelog([], actor.full_name, "Inspection method created."),
            name=name,
            label_color=cmd.label_color,
            label_font_color=cmd.label_font_color,
            description=description,
            creator_id=actor.id,
            creator=actor,
            default_setup_minutes=cmd.default_setup_minutes,
            default_minutes_per_piece=cmd.default_minutes_per_piece,
            requires_evidence=cmd.requires_evidence,
            default_machine_id=cmd.default_machine_id,
            sort_order=await self._inspection_methods.next_sort_order(),
        )
        saved = await self._inspection_methods.save(entity)
        await self._uow.commit()
        log.info(f"Created inspection method {shown_name(saved.name)!r}, ID={saved.id}.")
        return InspectionMethodMapper.to_result(saved)
