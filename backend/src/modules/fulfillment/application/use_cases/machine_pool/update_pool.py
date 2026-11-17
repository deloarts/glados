"""
Updates a machine pool's editable fields (name, machine composition, note), keeping the pool's
changelog and downstream event consumers in sync with what changed.
"""

from src.modules.catalogue.domain.errors import ProductionMachineNotFoundError
from src.modules.fulfillment.application.dto.machine_pool_dto import MachinePoolResult
from src.modules.fulfillment.application.dto.machine_pool_dto import UpdateMachinePoolCommand
from src.modules.fulfillment.application.mappers.machine_pool_mapper import MachinePoolMapper
from src.modules.fulfillment.domain.errors import MachinePoolNotFoundError
from src.modules.fulfillment.domain.events.machine_pool_events import MachinePoolUpdated
from src.modules.fulfillment.domain.services.machine_pool_rules import MachinePoolRules
from src.modules.fulfillment.ports.outbound.repositories.machine_pool_repository import (
    IMachinePoolRepository,
)
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


class UpdateMachinePool:
    def __init__(
        self,
        machine_pool_repo: IMachinePoolRepository,
        production_machine_repo: IProductionMachineRepository,
        *,
        event_bus: IEventBus,
        uow: IUnitOfWork,
        recompute_schedule: ScheduleRecompute | None = None,
    ) -> None:
        self._pools = machine_pool_repo
        self._machines = production_machine_repo
        self._bus = event_bus
        self._uow = uow
        self._recompute = recompute_schedule

    async def execute(
        self, actor: User, pool_id: int, cmd: UpdateMachinePoolCommand
    ) -> MachinePoolResult:
        MachinePoolRules.assert_can_update(actor)

        pool = found_or_raise(
            await self._pools.get_by_id(pool_id),
            MachinePoolNotFoundError,
            f"Machine pool #{pool_id} not found.",
        )

        if cmd.machine_ids is not None:
            for machine_id in cmd.machine_ids:
                if not await self._machines.get_by_id(machine_id):
                    raise ProductionMachineNotFoundError(
                        f"Production machine #{machine_id} not found."
                    )

        old = {
            "name": pool.name,
            "machine_ids": pool.machine_ids,
            "note": pool.note,
        }

        if cmd.name is not None:
            pool.name = cmd.name
        if cmd.machine_ids is not None:
            pool.machine_ids = cmd.machine_ids
        if cmd.note is not None:
            pool.note = cmd.note

        new = {
            "name": pool.name,
            "machine_ids": pool.machine_ids,
            "note": pool.note,
        }
        changelog_entry = diff_changes(old, new)

        pool.changed = now_utc()
        pool.changes = append_changelog(pool.changes, actor.full_name, changelog_entry)

        saved = await self._pools.save(pool)

        await self._bus.publish(
            MachinePoolUpdated(
                pool_id=saved.id,
                name=saved.name,
                actor_id=actor.id,
            )
        )
        await self._uow.commit()
        await recompute_schedule_after_commit(
            self._recompute, after="changing a machine pool; the change itself is committed."
        )

        log.info(f"Updated machine pool {saved.name!r}, ID={saved.id}.")

        return MachinePoolMapper.to_result(saved)
