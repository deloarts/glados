"""Updates lot fields (quantity, note, priority, required_delivery_date) with edit
constraints based on lot status.

The quantity is editable only while the lot is DRAFT, by the lot intent
table, and never below what made demands have allocated to the lot. A
supplier line of a position that is not ordered yet shrinks to its
position's new quantity. The lot's raw material demand follows in
proportion, by the rules of a direct
edit of that demand: it must still be open, and a counted unit takes whole
pieces only; when those refuse, the lot edit is refused with the same error. The lot
is locked through the request's lock plan before it is read, saved before
the project's time budgets are recomputed from it, and reconciled before the
commit.
"""

from datetime import datetime

from src.modules.fulfillment.application.dto.production_lot_dto import LotResult
from src.modules.fulfillment.application.dto.production_lot_dto import UpdateLotCommand
from src.modules.fulfillment.application.mappers.production_lot_mapper import LotMapper
from src.modules.fulfillment.application.services.lifecycle_reconciler import LifecycleReconciler
from src.modules.fulfillment.application.services.time_budget_propagation import BudgetOrders
from src.modules.fulfillment.application.services.time_budget_propagation import budget_order_locks
from src.modules.fulfillment.application.services.time_budget_propagation import (
    recompute_project_time_budgets,
)
from src.modules.fulfillment.application.use_cases.production_lot.lot_positions import locked_lot
from src.modules.fulfillment.domain.entities.order_item import OrderItem
from src.modules.fulfillment.domain.entities.production_lot import ProductionLot
from src.modules.fulfillment.domain.services.lot_event_service import build_lot_event
from src.modules.fulfillment.domain.services.lot_rules import LotRules
from src.modules.fulfillment.domain.services.lot_rules import assert_lot_action
from src.modules.fulfillment.domain.services.lot_rules import sync_position_quantities
from src.modules.fulfillment.domain.services.quantity_edit_rules import assert_lot_quantity_allowed
from src.modules.fulfillment.domain.services.source_item_demand_rules import (
    assert_source_demand_editable,
)
from src.modules.fulfillment.domain.value_objects.lifecycle_aggregate import LifecycleAggregate
from src.modules.fulfillment.domain.value_objects.lot_event_type import LotEventType
from src.modules.fulfillment.domain.value_objects.order_status import OrderItemStatus
from src.modules.fulfillment.ports.outbound.repositories.made_item_demand_repository import (
    IMadeItemAllocationRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.order_repository import (
    IOrderItemRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.production_lot_repository import (
    IProductionLotRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.production_order_repository import (
    IProductionOrderRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.source_item_demand_repository import (
    ISourceItemDemandRepository,
)
from src.modules.platform.application.services.schedule_recompute_port import ScheduleRecompute
from src.modules.platform.application.services.schedule_recompute_port import (
    recompute_schedule_after_commit,
)
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.services.edit_version import assert_edit_version
from src.modules.platform.domain.services.edit_version import bump_edit_version
from src.modules.platform.domain.services.quantities import assert_whole_pieces
from src.modules.platform.domain.services.quantities import quantity_gt
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork
from src.modules.workspace.ports.outbound.workspace_queries import IProjectQueries
from src.shared_kernel.domain.services.changelog_service import append_changelog
from src.shared_kernel.domain.services.changelog_service import diff_changes
from src.shared_kernel.domain.services.clock import now_utc
from src.shared_kernel.domain.value_objects.lifecycle_action import LifecycleAction

_NOT_ORDERED = frozenset({OrderItemStatus.PENDING, OrderItemStatus.REQUESTED})


class UpdateLot:
    def __init__(
        self,
        lot_repo: IProductionLotRepository,
        project_repo: IProjectQueries | None = None,
        *,
        uow: IUnitOfWork,
        reconciler: LifecycleReconciler,
        made_allocation_repo: IMadeItemAllocationRepository | None = None,
        source_item_demand_repo: ISourceItemDemandRepository | None = None,
        order_item_repo: IOrderItemRepository | None = None,
        order_repo: IProductionOrderRepository,
        recompute_schedule: ScheduleRecompute | None = None,
    ) -> None:
        """The production orders are the queued and paused ones of the
        project, whose duration a quantity edit's time budget recompute
        snapshots again; the schedule walk runs after the commit when one
        changed."""
        self._lots = lot_repo
        self._projects = project_repo
        self._orders = order_repo
        self._recompute = recompute_schedule
        self._uow = uow
        self._reconciler = reconciler
        self._made_allocations = made_allocation_repo
        self._source_item_demands = source_item_demand_repo
        self._order_items = order_item_repo

    async def execute(self, actor: User, lot_id: int, cmd: UpdateLotCommand) -> LotResult:
        # Locked, so the allocation guard below and the write see the same
        # lot.
        lot = await locked_lot(self._reconciler, self._lots, lot_id)
        LotRules.assert_can_update(actor, lot)
        assert_edit_version(lot, cmd.expected_edit_version, what=f"Lot #{lot.id}")

        # Snapshotted before mutation, then re-read off `lot` (not
        # cmd.model_dump()) after: quantity/note/priority all use "None
        # means leave unchanged" semantics, so diffing straight against the
        # command would read an omitted field as "changed to None".
        old = {
            "quantity": lot.quantity,
            "note": lot.note,
            "priority": lot.priority,
            "required_delivery_date": lot.required_delivery_date,
        }

        quantity_changed = False
        if cmd.quantity is not None and cmd.quantity != lot.quantity:
            quantity_changed = True
            assert_lot_action(LifecycleAction.EDIT_QUANTITY, lot, actor)
            if self._made_allocations is not None:
                allocations = await self._made_allocations.get_by_lot_id(lot.id)
                assert_lot_quantity_allowed(lot, cmd.quantity, sum(a.quantity for a in allocations))
            # The positions' supplier lines join the lock step of the input
            # demand, ahead of it in the lock order.
            lines = await self._live_made_lines(lot)
            self._reconciler.touch_order_items([line.id for line in lines])
            # The orders the time budget recompute may snapshot again sort
            # before the lines and demands, so they join the first lock.
            if self._projects is not None:
                await self._reconciler.lock_touched(
                    also=await budget_order_locks([lot.project_id], self._lots, self._orders)
                )
            await self._resize_input_demand(actor, lot, cmd.quantity)
            await self._reconciler.lock_touched()
            lot.quantity = cmd.quantity
            for position in sync_position_quantities(lot.positions, cmd.quantity):
                await self._lots.save_position(position)
            await self._shrink_unordered_lines(actor, lot, now_utc())

        if cmd.note is not None:
            lot.note = cmd.note
        if cmd.priority is not None:
            lot.priority = cmd.priority
        # Unlike note/priority (which can never be cleared through this
        # command), required_delivery_date needs a genuine clear path
        # ("revert to the demand-derived target"), so this checks whether
        # the field was actually provided in the request rather than
        # `is not None`, matching update_order.py's existing "provided"
        # pattern. Requires the endpoint to build cmd via
        # model_dump(exclude_unset=True), not a plain model_dump().
        if "required_delivery_date" in cmd.model_fields_set:
            lot.required_delivery_date = cmd.required_delivery_date

        new = {
            "quantity": lot.quantity,
            "note": lot.note,
            "priority": lot.priority,
            "required_delivery_date": lot.required_delivery_date,
        }
        changelog_entry = diff_changes(old, new, heading="Lot updated:")

        now = now_utc()
        bump_edit_version(lot)
        lot.changed = now
        lot.changes = append_changelog(lot.changes, actor.full_name, changelog_entry)
        await self._lots.record_event(
            build_lot_event(lot.id, actor, LotEventType.LOT_UPDATED, "lot", changelog_entry)
        )
        await self._lots.save(lot)
        self._reconciler.touch_lots([lot.id])
        await self._reconciler.run(actor, now)
        # Read from the saved lot, so the budgets follow its new quantity, and
        # after the reconciler's locks, since the time budget lock comes after
        # every lifecycle row a writer locks.
        touched_machine_ids: set[int | None] = set()
        if quantity_changed and self._projects is not None:
            touched_machine_ids = await recompute_project_time_budgets(
                lot.project_id,
                self._projects,
                self._lots,
                BudgetOrders(self._orders, self._reconciler.lock_plan),
            )
        await self._uow.commit()
        if touched_machine_ids:
            await recompute_schedule_after_commit(
                self._recompute, after=f"updating lot #{lot_id}; the update itself is committed."
            )

        log.info(f"Updated lot #{lot_id}.")
        result_lot = await self._lots.get_by_id(lot_id)
        assert result_lot is not None
        return LotMapper.to_result(result_lot)

    async def _live_made_lines(self, lot: ProductionLot) -> list[OrderItem]:
        if self._order_items is None or not lot.positions:
            return []
        lines = await self._order_items.get_by_lot_position_ids(
            sorted(p.id for p in lot.positions), refresh=True
        )
        return [line for line in lines if line.canceled_at is None]

    async def _shrink_unordered_lines(self, actor: User, lot: ProductionLot, now: datetime) -> None:
        """Shrinks a supplier line that is not ordered yet to its position's
        new quantity, so pieces the lot no longer needs are not ordered. An
        ordered line keeps its quantity; a lot with one is no DRAFT, so its
        quantity is not edited at all."""
        quantities = {p.id: p.quantity for p in lot.positions}
        for line in await self._live_made_lines(lot):
            if line.status not in _NOT_ORDERED or line.lot_position_id not in quantities:
                continue
            position_quantity = quantities[line.lot_position_id]
            if not quantity_gt(line.quantity, position_quantity):
                continue
            assert self._order_items is not None
            line.changes = append_changelog(
                line.changes,
                actor.full_name,
                f"Quantity {line.quantity:g} -> {position_quantity:g}, "
                f"lot {lot.lot_number!r} was resized.",
            )
            line.quantity = position_quantity
            line.changed = now
            await self._order_items.save(line)

    async def _resize_input_demand(
        self, actor: User, lot: ProductionLot, new_quantity: float
    ) -> None:
        """Resizes the lot's raw material demand in proportion to the new lot
        quantity, by the rules a direct edit of the demand follows, so a
        demand that is allocated, or a size that is no whole number of
        counted pieces, refuses the lot edit with the demand's own error."""
        if self._source_item_demands is None or lot.input_demand_id is None:
            return
        # The lot is touched with it, so the made demands the run derives
        # for the lot are locked in the same acquisition, ahead of the
        # source demand in the lock order.
        self._reconciler.touch_lots([lot.id])
        self._reconciler.touch_demands(LifecycleAggregate.SOURCE_DEMANDS, [lot.input_demand_id])
        await self._reconciler.lock_touched()
        demand = await self._source_item_demands.get_by_id(lot.input_demand_id)
        if demand is None:
            return
        assert_source_demand_editable(demand)
        resized = round(demand.quantity * new_quantity / lot.quantity, 6)
        assert_whole_pieces(resized, what="The demand quantity", unit=demand.unit)
        previous = demand.quantity
        demand.quantity = resized
        demand.changed = now_utc()
        demand.changes = append_changelog(
            demand.changes,
            actor.full_name,
            f"Quantity {previous:.3f} -> {resized:.3f} {demand.unit}, with lot {lot.lot_number!r}.",
        )
        await self._source_item_demands.save(demand)
