"""Use case for restoring an archived production machine and publishing
ProductionMachineRestored. No uniqueness pre-check: production machine has
no partial unique index scoped to `archived`, so restoring one can never
violate a live-row constraint."""

from src.modules.catalogue.domain.errors import ProductionMachineNotFoundError
from src.modules.fulfillment.application.dto.production_machine_dto import ProductionMachineResult
from src.modules.fulfillment.application.mappers.production_machine_mapper import (
    ProductionMachineMapper,
)
from src.modules.fulfillment.domain.entities.production_machine import ProductionMachine
from src.modules.fulfillment.domain.events.production_machine_events import (
    ProductionMachineRestored,
)
from src.modules.fulfillment.domain.services.production_machine_rules import ProductionMachineRules
from src.modules.fulfillment.ports.outbound.repositories.production_machine_repository import (
    IProductionMachineRepository,
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


class RestoreProductionMachine:
    def __init__(
        self,
        machine_repo: IProductionMachineRepository,
        *,
        event_bus: IEventBus,
        uow: IUnitOfWork,
        recompute_schedule: ScheduleRecompute | None = None,
    ) -> None:
        self._machines = machine_repo
        self._bus = event_bus
        self._uow = uow
        self._recompute = recompute_schedule

    async def execute(self, actor: User, machine_id: int) -> ProductionMachineResult:
        ProductionMachineRules.assert_can_restore(actor)

        async def _before_save(machine: ProductionMachine) -> None:
            machine.changed = now_utc()
            machine.changes = append_changelog(
                machine.changes, actor.full_name, "Machine restored."
            )

        saved = await set_archived(
            entity_id=machine_id,
            archived=False,
            load=self._machines.get_by_id,
            not_found=lambda mid: ProductionMachineNotFoundError(
                f"Production machine #{mid} not found."
            ),
            save=self._machines.save,
            before_save=_before_save,
        )

        await self._bus.publish(
            ProductionMachineRestored(
                machine_id=saved.id,
                internal_name=saved.internal_name,
                actor_id=actor.id,
            )
        )
        await self._uow.commit()
        await recompute_schedule_after_commit(
            self._recompute, after="restoring a machine; the change itself is committed."
        )

        log.info(f"Restored production machine {saved.internal_name!r}, ID={saved.id}.")

        return ProductionMachineMapper.to_result(saved)
