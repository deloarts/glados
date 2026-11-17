"""
No uniqueness pre-check: machine pool has no partial unique index scoped
to `archived`, so restoring one can never violate a live-row constraint.
"""

from src.modules.fulfillment.application.dto.machine_pool_dto import MachinePoolResult
from src.modules.fulfillment.application.mappers.machine_pool_mapper import MachinePoolMapper
from src.modules.fulfillment.domain.entities.machine_pool import MachinePool
from src.modules.fulfillment.domain.errors import MachinePoolNotFoundError
from src.modules.fulfillment.domain.events.machine_pool_events import MachinePoolRestored
from src.modules.fulfillment.domain.services.machine_pool_rules import MachinePoolRules
from src.modules.fulfillment.ports.outbound.repositories.machine_pool_repository import (
    IMachinePoolRepository,
)
from src.modules.platform.application.services.archive_restore import set_archived
from src.modules.platform.application.services.schedule_recompute_port import ScheduleRecompute
from src.modules.platform.application.services.schedule_recompute_port import (
    recompute_schedule_after_commit,
)
from src.modules.platform.domain.entities.user import User
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.ports.outbound.event_bus_port import IEventBus
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork
from src.shared_kernel.domain.services.changelog_service import append_changelog
from src.shared_kernel.domain.services.clock import now_utc


class RestoreMachinePool:
    def __init__(
        self,
        machine_pool_repo: IMachinePoolRepository,
        *,
        event_bus: IEventBus,
        uow: IUnitOfWork,
        recompute_schedule: ScheduleRecompute | None = None,
    ) -> None:
        self._pools = machine_pool_repo
        self._bus = event_bus
        self._uow = uow
        self._recompute = recompute_schedule

    async def execute(self, actor: User, pool_id: int) -> MachinePoolResult:
        MachinePoolRules.assert_can_restore(actor)

        async def _before_save(pool: MachinePool) -> None:
            pool.changed = now_utc()
            pool.changes = append_changelog(pool.changes, actor.full_name, "Machine pool restored.")

        saved = await set_archived(
            entity_id=pool_id,
            archived=False,
            load=self._pools.get_by_id,
            not_found=lambda pid: MachinePoolNotFoundError(f"Machine pool #{pid} not found."),
            save=self._pools.save,
            before_save=_before_save,
        )

        await self._bus.publish(
            MachinePoolRestored(
                pool_id=saved.id,
                name=saved.name,
                actor_id=actor.id,
            )
        )
        await self._uow.commit()
        await recompute_schedule_after_commit(
            self._recompute, after="restoring a machine pool; the change itself is committed."
        )

        log.info(f"Restored machine pool {saved.name!r}, ID={saved.id}.")

        return MachinePoolMapper.to_result(saved)
