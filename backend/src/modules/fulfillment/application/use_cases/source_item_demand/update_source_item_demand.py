"""
Edits a source item demand until it is fulfilled or canceled, as bought and
made demands are edited: its note, dates and flags at any time, and its
quantity never below what its allocations already cover. The lifecycle
reconciler derives the demand's status after the edit.
"""

from src.modules.fulfillment.application.dto.source_item_demand_dto import SourceItemDemandResult
from src.modules.fulfillment.application.dto.source_item_demand_dto import (
    UpdateSourceItemDemandCommand,
)
from src.modules.fulfillment.application.mappers.source_item_demand_mapper import (
    SourceItemDemandMapper,
)
from src.modules.fulfillment.application.services.lifecycle_reconciler import LifecycleReconciler
from src.modules.fulfillment.application.use_cases._demand_family.spec import QUANTITY_REASON
from src.modules.fulfillment.domain.errors import SourceItemDemandNotFoundError
from src.modules.fulfillment.domain.services.lot_rules import LotRules
from src.modules.fulfillment.domain.services.quantity_edit_rules import (
    assert_demand_quantity_allowed,
)
from src.modules.fulfillment.domain.services.source_item_allocation_service import (
    SourceItemAllocationRules,
)
from src.modules.fulfillment.domain.value_objects.lifecycle_aggregate import LifecycleAggregate
from src.modules.fulfillment.ports.outbound.repositories.production_lot_repository import (
    IProductionLotRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.source_item_demand_repository import (
    ISourceItemAllocationRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.source_item_demand_repository import (
    ISourceItemDemandRepository,
)
from src.modules.platform.application.services.command_changelog import diff_command
from src.modules.platform.application.services.lookup import found_or_raise
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.services.crud_permission_rules import assert_has_permission
from src.modules.platform.domain.services.quantities import assert_whole_pieces
from src.modules.platform.domain.value_objects.permission import Permission
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork
from src.shared_kernel.domain.services.changelog_service import append_changelog
from src.shared_kernel.domain.services.clock import now_utc


class UpdateSourceItemDemand:
    def __init__(
        self,
        demand_repo: ISourceItemDemandRepository,
        lot_repo: IProductionLotRepository,
        *,
        allocation_repo: ISourceItemAllocationRepository,
        uow: IUnitOfWork,
        reconciler: LifecycleReconciler,
    ) -> None:
        self._demands = demand_repo
        self._lots = lot_repo
        self._allocations = allocation_repo
        self._uow = uow
        self._reconciler = reconciler

    async def execute(
        self, actor: User, demand_id: int, cmd: UpdateSourceItemDemandCommand
    ) -> SourceItemDemandResult:
        # Locked before it is read, as the allocation writers lock it, so the
        # state checked below and the allocations the reconciler counts stay
        # as read until the commit.
        self._reconciler.touch_demands(LifecycleAggregate.SOURCE_DEMANDS, [demand_id])
        await self._reconciler.lock_touched()
        demand = found_or_raise(
            await self._demands.get_by_id(demand_id),
            SourceItemDemandNotFoundError,
            f"Source item demand #{demand_id} not found.",
        )
        SourceItemAllocationRules.assert_not_terminal(demand)

        # Fail-closed: a dangling lot_id must not skip the permission check
        # entirely, it falls back to a bare write:lots requirement instead.
        lot = await self._lots.get_by_id(demand.lot_id)
        if lot:
            LotRules.assert_can_update(actor, lot)
        else:
            assert_has_permission(actor, Permission.WRITE_LOTS, "update", "source item demands")

        if cmd.quantity != demand.quantity or cmd.unit != demand.unit:
            assert_whole_pieces(cmd.quantity, what="The demand quantity", unit=cmd.unit)
        assert_demand_quantity_allowed(
            demand,
            cmd.quantity,
            await self._allocations.get_allocated_quantity(demand.id),
            noun="Source item demand",
        )
        changelog_entry = diff_command(demand, cmd)

        demand.quantity = cmd.quantity
        demand.unit = cmd.unit
        demand.items_per_unit = cmd.items_per_unit
        demand.high_priority = cmd.high_priority
        demand.notify_on_delivery = cmd.notify_on_delivery
        demand.note = cmd.note
        demand.desired_delivery_date = cmd.desired_delivery_date
        demand.changed = now_utc()
        demand.changes = append_changelog(demand.changes, actor.full_name, changelog_entry)

        saved = await self._demands.save(demand)
        self._reconciler.touch_demands(LifecycleAggregate.SOURCE_DEMANDS, [saved.id])
        result = await self._reconciler.run(actor, now_utc(), reason=QUANTITY_REASON)
        if result.changed_ids(LifecycleAggregate.SOURCE_DEMANDS):
            saved = await self._demands.get_by_id(saved.id) or saved
        await self._uow.commit()
        log.info(f"Updated source item demand #{saved.id}.")
        return SourceItemDemandMapper.to_result(saved)
