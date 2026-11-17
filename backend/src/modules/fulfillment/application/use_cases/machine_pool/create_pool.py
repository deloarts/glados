"""
Creates a new machine pool from a set of production machines, recording the creation in the
pool's changelog and publishing MachinePoolCreated.
"""

from src.modules.catalogue.domain.errors import ProductionMachineNotFoundError
from src.modules.fulfillment.application.dto.machine_pool_dto import CreateMachinePoolCommand
from src.modules.fulfillment.application.dto.machine_pool_dto import MachinePoolResult
from src.modules.fulfillment.application.mappers.machine_pool_mapper import MachinePoolMapper
from src.modules.fulfillment.domain.entities.machine_pool import MachinePool
from src.modules.fulfillment.domain.events.machine_pool_events import MachinePoolCreated
from src.modules.fulfillment.domain.services.machine_pool_rules import MachinePoolRules
from src.modules.fulfillment.ports.outbound.repositories.machine_pool_repository import (
    IMachinePoolRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.production_machine_repository import (
    IProductionMachineRepository,
)
from src.modules.platform.domain.entities.user import User
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.ports.outbound.event_bus_port import IEventBus
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork
from src.shared_kernel.domain.services.changelog_service import append_changelog
from src.shared_kernel.domain.services.clock import now_utc


class CreateMachinePool:
    def __init__(
        self,
        machine_pool_repo: IMachinePoolRepository,
        production_machine_repo: IProductionMachineRepository,
        *,
        event_bus: IEventBus,
        uow: IUnitOfWork,
    ) -> None:
        self._pools = machine_pool_repo
        self._machines = production_machine_repo
        self._bus = event_bus
        self._uow = uow

    async def execute(self, actor: User, cmd: CreateMachinePoolCommand) -> MachinePoolResult:
        MachinePoolRules.assert_can_create(actor)

        for machine_id in cmd.machine_ids:
            if not await self._machines.get_by_id(machine_id):
                raise ProductionMachineNotFoundError(f"Production machine #{machine_id} not found.")

        now = now_utc()
        pool = MachinePool(
            id=0,
            created=now,
            changed=now,
            changes=append_changelog([], actor.full_name, "Machine pool created."),
            archived=False,
            name=cmd.name,
            machine_ids=cmd.machine_ids,
            note=cmd.note,
            sort_order=await self._pools.next_sort_order(),
            creator_id=actor.id,
            creator_full_name=actor.full_name,
        )

        saved = await self._pools.save(pool)

        await self._bus.publish(
            MachinePoolCreated(
                pool_id=saved.id,
                name=saved.name,
                actor_id=actor.id,
            )
        )
        await self._uow.commit()

        log.info(f"Created machine pool {saved.name!r}, ID={saved.id}.")

        return MachinePoolMapper.to_result(saved)
