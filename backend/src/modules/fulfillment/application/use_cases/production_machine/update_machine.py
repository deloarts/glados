"""Use case for updating a production machine's fields."""

from src.modules.catalogue.domain.errors import FabricationMethodNotFoundError
from src.modules.catalogue.domain.errors import ProductionMachineNotFoundError
from src.modules.catalogue.ports.outbound.catalogue_queries import IFabricationMethodQueries
from src.modules.fulfillment.application.dto.production_machine_dto import ProductionMachineResult
from src.modules.fulfillment.application.dto.production_machine_dto import (
    UpdateProductionMachineCommand,
)
from src.modules.fulfillment.application.mappers.production_machine_mapper import (
    ProductionMachineMapper,
)
from src.modules.fulfillment.domain.events.production_machine_events import ProductionMachineUpdated
from src.modules.fulfillment.domain.services.production_machine_rules import ProductionMachineRules
from src.modules.fulfillment.ports.outbound.repositories.production_machine_repository import (
    IProductionMachineRepository,
)
from src.modules.platform.application.services.lookup import found_or_raise
from src.modules.platform.application.services.schedule_recompute_port import ScheduleRecompute
from src.modules.platform.application.services.schedule_recompute_port import (
    recompute_schedule_after_commit,
)
from src.modules.platform.domain.entities.user import User
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.ports.outbound.event_bus_port import IEventBus
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork
from src.shared_kernel.domain.services.changelog_service import append_changelog
from src.shared_kernel.domain.services.changelog_service import diff_changes
from src.shared_kernel.domain.services.clock import now_utc


class UpdateProductionMachine:
    def __init__(
        self,
        machine_repo: IProductionMachineRepository,
        fabrication_method_repo: IFabricationMethodQueries,
        *,
        event_bus: IEventBus,
        uow: IUnitOfWork,
        recompute_schedule: ScheduleRecompute | None = None,
    ) -> None:
        self._machines = machine_repo
        self._fabrication_methods = fabrication_method_repo
        self._bus = event_bus
        self._uow = uow
        self._recompute = recompute_schedule

    async def execute(
        self, actor: User, machine_id: int, cmd: UpdateProductionMachineCommand
    ) -> ProductionMachineResult:
        ProductionMachineRules.assert_can_update(actor)

        machine = found_or_raise(
            await self._machines.get_by_id(machine_id),
            ProductionMachineNotFoundError,
            f"Production machine #{machine_id} not found.",
        )

        if cmd.fabrication_method_ids is not None:
            for fabrication_method_id in cmd.fabrication_method_ids:
                if not await self._fabrication_methods.get_by_id(fabrication_method_id):
                    raise FabricationMethodNotFoundError(
                        f"Fabrication method #{fabrication_method_id} not found."
                    )

        old = {
            "internal_name": machine.internal_name,
            "vendor": machine.vendor,
            "model": machine.model,
            "fabrication_method_ids": machine.fabrication_method_ids,
            "max_part_dimension": machine.max_part_dimension,
            "note": machine.note,
            "is_qa_machine": machine.is_qa_machine,
        }

        if cmd.internal_name is not None:
            machine.internal_name = cmd.internal_name
        if cmd.vendor is not None:
            machine.vendor = cmd.vendor
        if cmd.model is not None:
            machine.model = cmd.model
        if cmd.fabrication_method_ids is not None:
            machine.fabrication_method_ids = cmd.fabrication_method_ids
        if cmd.max_part_dimension is not None:
            machine.max_part_dimension = cmd.max_part_dimension
        if cmd.note is not None:
            machine.note = cmd.note
        if cmd.is_qa_machine is not None:
            machine.is_qa_machine = cmd.is_qa_machine

        new = {
            "internal_name": machine.internal_name,
            "vendor": machine.vendor,
            "model": machine.model,
            "fabrication_method_ids": machine.fabrication_method_ids,
            "max_part_dimension": machine.max_part_dimension,
            "note": machine.note,
            "is_qa_machine": machine.is_qa_machine,
        }
        changelog_entry = diff_changes(old, new)

        machine.changed = now_utc()
        machine.changes = append_changelog(machine.changes, actor.full_name, changelog_entry)

        saved = await self._machines.save(machine)

        await self._bus.publish(
            ProductionMachineUpdated(
                machine_id=saved.id,
                internal_name=saved.internal_name,
                actor_id=actor.id,
            )
        )
        await self._uow.commit()
        await recompute_schedule_after_commit(
            self._recompute, after="changing a machine; the change itself is committed."
        )

        log.info(f"Updated production machine {saved.internal_name!r}, ID={saved.id}.")

        return ProductionMachineMapper.to_result(saved)
