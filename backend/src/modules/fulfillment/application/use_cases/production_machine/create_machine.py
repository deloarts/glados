"""Use case for creating a production machine and validating its fabrication method."""

from src.modules.catalogue.domain.errors import FabricationMethodNotFoundError
from src.modules.catalogue.ports.outbound.catalogue_queries import IFabricationMethodQueries
from src.modules.fulfillment.application.dto.production_machine_dto import (
    CreateProductionMachineCommand,
)
from src.modules.fulfillment.application.dto.production_machine_dto import ProductionMachineResult
from src.modules.fulfillment.application.mappers.production_machine_mapper import (
    ProductionMachineMapper,
)
from src.modules.fulfillment.domain.entities.production_machine import ProductionMachine
from src.modules.fulfillment.domain.events.production_machine_events import ProductionMachineCreated
from src.modules.fulfillment.domain.services.production_machine_rules import ProductionMachineRules
from src.modules.fulfillment.ports.outbound.repositories.production_machine_repository import (
    IProductionMachineRepository,
)
from src.modules.platform.domain.entities.user import User
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.ports.outbound.event_bus_port import IEventBus
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork
from src.shared_kernel.domain.services.changelog_service import append_changelog
from src.shared_kernel.domain.services.clock import now_utc


class CreateProductionMachine:
    def __init__(
        self,
        machine_repo: IProductionMachineRepository,
        fabrication_method_repo: IFabricationMethodQueries,
        *,
        event_bus: IEventBus,
        uow: IUnitOfWork,
    ) -> None:
        self._machines = machine_repo
        self._fabrication_methods = fabrication_method_repo
        self._bus = event_bus
        self._uow = uow

    async def execute(
        self, actor: User, cmd: CreateProductionMachineCommand
    ) -> ProductionMachineResult:
        ProductionMachineRules.assert_can_create(actor)

        for fabrication_method_id in cmd.fabrication_method_ids:
            if not await self._fabrication_methods.get_by_id(fabrication_method_id):
                raise FabricationMethodNotFoundError(
                    f"Fabrication method #{fabrication_method_id} not found."
                )

        now = now_utc()
        machine = ProductionMachine(
            id=0,
            created=now,
            changed=now,
            changes=append_changelog([], actor.full_name, "Machine created."),
            archived=False,
            internal_name=cmd.internal_name,
            vendor=cmd.vendor,
            model=cmd.model,
            fabrication_method_ids=cmd.fabrication_method_ids,
            max_part_dimension=cmd.max_part_dimension,
            note=cmd.note,
            is_qa_machine=cmd.is_qa_machine,
            sort_order=await self._machines.next_sort_order(),
            creator_id=actor.id,
            creator_full_name=actor.full_name,
        )

        saved = await self._machines.save(machine)

        await self._bus.publish(
            ProductionMachineCreated(
                machine_id=saved.id,
                internal_name=saved.internal_name,
                actor_id=actor.id,
            )
        )
        await self._uow.commit()

        log.info(f"Created production machine {saved.internal_name!r}, ID={saved.id}.")

        return ProductionMachineMapper.to_result(saved)
