"""Use case for archiving a production machine and publishing ProductionMachineArchived.

A machine with queued, in-progress or paused production orders is not archived: the planning
and queue boards hide an archived machine, and its orders would vanish with it. Those orders are
moved to another machine or finished first; the refusal counts them.

The archive takes the machine's queue lock before it counts. Every writer that queues an order on
a machine holds that lock and refuses an archived machine under it (assert_machine_takes_work),
so an order cannot land on the machine between the count and the commit.
"""

from src.modules.catalogue.domain.errors import ProductionMachineNotFoundError
from src.modules.fulfillment.application.dto.production_machine_dto import ProductionMachineResult
from src.modules.fulfillment.application.mappers.production_machine_mapper import (
    ProductionMachineMapper,
)
from src.modules.fulfillment.domain.entities.production_machine import ProductionMachine
from src.modules.fulfillment.domain.errors import ProductionMachineArchiveBlockedError
from src.modules.fulfillment.domain.events.production_machine_events import (
    ProductionMachineArchived,
)
from src.modules.fulfillment.domain.services.production_machine_rules import ProductionMachineRules
from src.modules.fulfillment.ports.outbound.repositories.production_machine_repository import (
    IProductionMachineRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.production_order_repository import (
    IProductionOrderRepository,
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


class ArchiveProductionMachine:
    def __init__(
        self,
        machine_repo: IProductionMachineRepository,
        order_repo: IProductionOrderRepository,
        *,
        event_bus: IEventBus,
        uow: IUnitOfWork,
        recompute_schedule: ScheduleRecompute | None = None,
    ) -> None:
        self._machines = machine_repo
        self._orders = order_repo
        self._bus = event_bus
        self._uow = uow
        self._recompute = recompute_schedule

    async def execute(self, actor: User, machine_id: int) -> ProductionMachineResult:
        ProductionMachineRules.assert_can_archive(actor)
        await self._orders.lock_queue_scope(machine_id, None)

        async def _before_save(machine: ProductionMachine) -> None:
            live = (await self._orders.count_live_by_machine_ids([machine.id])).get(machine.id, 0)
            if live:
                orders = "production order" if live == 1 else "production orders"
                raise ProductionMachineArchiveBlockedError(
                    f"Production machine {machine.internal_name!r} still has {live} {orders} "
                    "queued, in progress or paused. Move them to another machine or finish "
                    "them before archiving the machine."
                )
            machine.changed = now_utc()
            machine.changes = append_changelog(
                machine.changes, actor.full_name, "Machine archived."
            )

        saved = await set_archived(
            entity_id=machine_id,
            archived=True,
            load=self._machines.get_by_id,
            not_found=lambda mid: ProductionMachineNotFoundError(
                f"Production machine #{mid} not found."
            ),
            save=self._machines.save,
            before_save=_before_save,
        )

        await self._bus.publish(
            ProductionMachineArchived(
                machine_id=saved.id,
                internal_name=saved.internal_name,
                actor_id=actor.id,
            )
        )
        await self._uow.commit()
        await recompute_schedule_after_commit(
            self._recompute, after="archiving a machine; the change itself is committed."
        )

        log.info(f"Archived production machine {saved.internal_name!r}, ID={saved.id}.")

        return ProductionMachineMapper.to_result(saved)
