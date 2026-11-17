"""Assigns a lot position to in-house production: creates one queued order
per machine or pool in the quantity split, in one transaction, appended to
the back of each queue. A position takes production orders for at most its
remaining quantity, whatever it already has, so a partly queued or partly
bought position can be topped up.

The target queues are locked first, then the lot through the request's lock
plan before the position is read, and the lifecycle reconciler derives the
position's kind and status and the lot's status from the new orders before
the project's time budgets are recomputed, since a position's kind decides
whether it counts towards them.
"""

from datetime import datetime

from src.modules.catalogue.domain.errors import ProductionMachineNotFoundError
from src.modules.fulfillment.application.dto.production_lot_dto import LotPositionResult
from src.modules.fulfillment.application.dto.production_order_dto import (
    AssignInternalPositionCommand,
)
from src.modules.fulfillment.application.mappers.production_lot_mapper import LotPositionMapper
from src.modules.fulfillment.application.services.lifecycle_loader import AggregateIds
from src.modules.fulfillment.application.services.lifecycle_reconciler import LifecycleReconciler
from src.modules.fulfillment.application.services.production_order_factory import (
    build_queued_production_order,
)
from src.modules.fulfillment.application.services.queue_scope_locks import lock_queue_scopes_first
from src.modules.fulfillment.application.services.time_budget_propagation import BudgetOrders
from src.modules.fulfillment.application.services.time_budget_propagation import budget_order_locks
from src.modules.fulfillment.application.services.time_budget_propagation import (
    recompute_project_time_budgets,
)
from src.modules.fulfillment.application.use_cases.production_schedule.recompute_machine_schedule import (
    RecomputeMachineSchedule,
)
from src.modules.fulfillment.domain.entities.lot_position import LotPosition
from src.modules.fulfillment.domain.entities.production_lot import ProductionLot
from src.modules.fulfillment.domain.entities.production_order import ProductionOrder
from src.modules.fulfillment.domain.errors import LotInvalidStatusTransitionError
from src.modules.fulfillment.domain.errors import LotPositionNotAssignableError
from src.modules.fulfillment.domain.errors import LotPositionNotFoundError
from src.modules.fulfillment.domain.errors import MachinePoolNotFoundError
from src.modules.fulfillment.domain.errors import ProductionOrderQuantityOverflowError
from src.modules.fulfillment.domain.events.production_order_events import ProductionOrderCreated
from src.modules.fulfillment.domain.services.lot_event_service import build_lot_event
from src.modules.fulfillment.domain.services.lot_rules import PositionRefusal
from src.modules.fulfillment.domain.services.lot_rules import lot_position_context
from src.modules.fulfillment.domain.services.lot_rules import lot_position_refusal
from src.modules.fulfillment.domain.services.production_order_rules import ProductionOrderRules
from src.modules.fulfillment.domain.services.production_order_rules import assert_capability_match
from src.modules.fulfillment.domain.services.production_order_rules import (
    assert_machine_or_pool_assigned,
)
from src.modules.fulfillment.domain.services.production_order_rules import assert_machine_takes_work
from src.modules.fulfillment.domain.services.production_order_rules import (
    assert_pool_capability_match,
)
from src.modules.fulfillment.domain.services.production_order_rules import (
    assert_quantity_within_position,
)
from src.modules.fulfillment.domain.services.production_order_rules import (
    compute_estimated_duration_minutes,
)
from src.modules.fulfillment.domain.value_objects.lifecycle_aggregate import LifecycleAggregate
from src.modules.fulfillment.domain.value_objects.lot_event_type import LotEventType
from src.modules.fulfillment.ports.outbound.fulfillment_settings_repository import (
    IFulfillmentSettingsRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.machine_pool_repository import (
    IMachinePoolRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.production_lot_repository import (
    IProductionLotRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.production_machine_repository import (
    IProductionMachineRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.production_order_repository import (
    IProductionOrderRepository,
)
from src.modules.platform.application.services.lookup import found_or_raise
from src.modules.platform.application.services.retry_on_conflict import (
    commit_or_raise_numbering_conflict,
)
from src.modules.platform.application.services.schedule_recompute_port import (
    recompute_schedule_after_commit,
)
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.services.quantities import assert_whole_pieces
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.ports.outbound.event_bus_port import IEventBus
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork
from src.modules.workspace.ports.outbound.workspace_queries import IProjectQueries
from src.shared_kernel.domain.services.clock import now_utc
from src.shared_kernel.domain.value_objects.lifecycle_action import LifecycleAction


class AssignInternalPosition:
    def __init__(
        self,
        lot_repo: IProductionLotRepository,
        machine_repo: IProductionMachineRepository,
        order_repo: IProductionOrderRepository,
        settings_repo: IFulfillmentSettingsRepository,
        recompute_schedule: RecomputeMachineSchedule | None = None,
        project_repo: IProjectQueries | None = None,
        pool_repo: IMachinePoolRepository | None = None,
        *,
        event_bus: IEventBus,
        uow: IUnitOfWork,
        reconciler: LifecycleReconciler,
    ) -> None:
        self._lots = lot_repo
        self._machines = machine_repo
        self._orders = order_repo
        self._settings = settings_repo
        self._recompute = recompute_schedule
        self._projects = project_repo
        self._pools = pool_repo
        self._bus = event_bus
        self._uow = uow
        self._reconciler = reconciler

    async def execute(
        self, actor: User, lot_id: int, position_id: int, cmd: AssignInternalPositionCommand
    ) -> LotPositionResult:
        ProductionOrderRules.assert_can_assign(actor)

        # The target queues are locked before the lot, as every writer that
        # draws queue places does (queue_scope_locks.py).
        await lock_queue_scopes_first(
            self._orders, [(o.machine_id, o.machine_pool_id) for o in cmd.orders]
        )
        lot = await self._load_and_lock_lot(lot_id)
        position = await self._load_and_validate_position(lot_id, position_id)
        total_requested = self._assert_assignable(actor, lot, position, cmd)
        await self._validate_machines_and_pools(position, cmd)

        now = now_utc()
        created_orders = await self._create_orders(actor, position, lot, cmd, now)
        self._reconciler.touch_positions([position_id])
        await self._record_assignment_event(
            actor, lot_id, position_id, position, created_orders, total_requested
        )
        await self._reconciler.run(actor, now)
        await self._recompute_time_budgets(lot, position_id, created_orders)

        await self._publish_assignment_events(actor, created_orders, position)
        await commit_or_raise_numbering_conflict(self._uow)
        await self._recompute_schedule_after_commit(created_orders, position_id)

        log.info(
            f"Assigned position #{position_id} of lot #{lot_id} "
            f"to {len(created_orders)} production order(s)."
        )
        result_position = found_or_raise(
            await self._lots.get_position_by_id(position_id),
            LotPositionNotFoundError,
            f"Position #{position_id} not found after save.",
        )
        return LotPositionMapper.to_result(result_position)

    async def _load_and_lock_lot(self, lot_id: int) -> ProductionLot:
        # Locked first, so the remaining-quantity check cannot race another
        # completion or assignment; the position is re-read under the lock.
        # The queued and paused orders of the lot's project join the lock,
        # since the time budget recompute may snapshot them again; a lot
        # never changes its project, so the read before the lock names it.
        locks = AggregateIds.of({LifecycleAggregate.LOTS: [lot_id]})
        unlocked = await self._lots.get_by_id(lot_id) if self._projects is not None else None
        if unlocked is not None:
            locks = locks.union(
                await budget_order_locks([unlocked.project_id], self._lots, self._orders)
            )
        await self._reconciler.lock_touched(also=locks)
        return found_or_raise(
            await self._lots.get_by_id_for_update(lot_id),
            LotPositionNotFoundError,
            f"Lot #{lot_id} not found.",
        )

    async def _load_and_validate_position(self, lot_id: int, position_id: int) -> LotPosition:
        position = await self._lots.get_position_by_id(position_id)
        if not position or position.lot_id != lot_id:
            raise LotPositionNotFoundError(f"Position #{position_id} not found on lot #{lot_id}.")
        return position

    def _assert_assignable(
        self,
        actor: User,
        lot: ProductionLot,
        position: LotPosition,
        cmd: AssignInternalPositionCommand,
    ) -> float:
        """The assign internal rule of the lot position intent table: the lot
        is not finished and the position has quantity left. A finished lot
        answers 422 as it always has, a position with nothing left answers
        the overflow 422, and any other refusal of the rule a 409. The
        requested quantity must then fit the remaining one (422 otherwise)."""
        context = lot_position_context(position, lot.status)
        refusal = lot_position_refusal(LifecycleAction.ASSIGN_INTERNAL, position, context, actor)
        if refusal is PositionRefusal.LOT_TERMINAL:
            raise LotInvalidStatusTransitionError(
                f"Lot #{lot.id} is {lot.status.value} and cannot be assigned new production orders."
            )
        if refusal is PositionRefusal.NOTHING_REMAINING:
            raise ProductionOrderQuantityOverflowError(
                f"Position #{position.id} has nothing left to assign; its live orders and line "
                "already cover its quantity."
            )
        if refusal is not None:
            raise LotPositionNotAssignableError(
                f"Position #{position.id} cannot be assigned to production orders now."
            )
        for order_input in cmd.orders:
            assert_whole_pieces(order_input.quantity, what="The production order quantity")
        total_requested = sum(o.quantity for o in cmd.orders)
        assert_quantity_within_position(0.0, total_requested, context.remaining)
        return total_requested

    async def _validate_machines_and_pools(
        self, position: LotPosition, cmd: AssignInternalPositionCommand
    ) -> None:
        machines = {}
        pools = {}
        for order_input in cmd.orders:
            assert_machine_or_pool_assigned(
                position.steps, order_input.machine_id, order_input.machine_pool_id
            )
            if order_input.machine_id is not None:
                if order_input.machine_id not in machines:
                    machine = await self._machines.get_by_id(order_input.machine_id)
                    if not machine:
                        raise ProductionMachineNotFoundError(
                            f"Machine #{order_input.machine_id} not found."
                        )
                    assert_machine_takes_work(machine)
                    assert_capability_match(machine, position.steps)
                    machines[order_input.machine_id] = machine
            elif order_input.machine_pool_id is not None:  # noqa: SIM102 - merging into the
                # elif condition reads correctly here (this is the chain's last branch), but
                # this is machine/pool assignment logic for production orders; left nested
                # rather than risk a subtly wrong merge under an if/elif chain.
                if order_input.machine_pool_id not in pools:
                    if self._pools is None:
                        raise MachinePoolNotFoundError(
                            f"Machine pool #{order_input.machine_pool_id} not found."
                        )
                    pool = await self._pools.get_by_id(order_input.machine_pool_id)
                    if not pool:
                        raise MachinePoolNotFoundError(
                            f"Machine pool #{order_input.machine_pool_id} not found."
                        )
                    assert_pool_capability_match(pool, position.steps)
                    pools[order_input.machine_pool_id] = pool

    async def _create_orders(
        self,
        actor: User,
        position: LotPosition,
        lot: ProductionLot,
        cmd: AssignInternalPositionCommand,
        now: datetime,
    ) -> list[ProductionOrder]:
        template = (await self._settings.get_production()).production_order_number_format
        created_orders = []
        for order_input in cmd.orders:
            changelog_note = (
                f"Queued on machine #{order_input.machine_id}."
                if order_input.machine_id is not None
                else (
                    f"Queued on machine pool #{order_input.machine_pool_id}."
                    if order_input.machine_pool_id is not None
                    # Only manual or inspection positions get here.
                    else "Queued with no machine assigned."
                )
            )
            saved_order = await build_queued_production_order(
                actor,
                position,
                order_input.quantity,
                lot.priority,
                machine_id=order_input.machine_id,
                machine_pool_id=order_input.machine_pool_id,
                order_repo=self._orders,
                number_template=template,
                now=now,
                changelog_note=changelog_note,
            )
            created_orders.append(saved_order)
            self._reconciler.touch_production_orders([saved_order.id], created=True)
        return created_orders

    async def _record_assignment_event(
        self,
        actor: User,
        lot_id: int,
        position_id: int,
        position: LotPosition,
        created_orders: list[ProductionOrder],
        total_requested: float,
    ) -> None:
        await self._lots.record_event(
            build_lot_event(
                lot_id,
                actor,
                LotEventType.POSITION_ASSIGNED_INTERNAL,
                "position",
                f"Position #{position_id} assigned to {len(created_orders)} production "
                f"order(s) ({total_requested:.3f}/{position.quantity:.3f} queued).",
                entity_id=position_id,
                payload={"production_order_ids": [o.id for o in created_orders]},
            )
        )

    async def _recompute_time_budgets(
        self, lot: ProductionLot, position_id: int, created_orders: list[ProductionOrder]
    ) -> None:
        # The position may just have become eligible for the time budget.
        # This runs before the duration snapshot, or orders without a
        # measured time would be sized at zero. The orders are read as the
        # reconciler left them, so a save writes no older status back.
        if self._projects is not None:
            await recompute_project_time_budgets(
                lot.project_id,
                self._projects,
                self._lots,
                BudgetOrders(self._orders, self._reconciler.lock_plan),
            )

            refreshed_position = await self._lots.get_position_by_id(position_id)
            if refreshed_position:
                orders = await self._orders.get_by_ids([o.id for o in created_orders])
                for order in orders:
                    new_duration = compute_estimated_duration_minutes(
                        refreshed_position.steps, order.quantity
                    )
                    if new_duration != order.estimated_duration_minutes:
                        order.estimated_duration_minutes = new_duration
                        await self._orders.save(order)

    async def _publish_assignment_events(
        self,
        actor: User,
        created_orders: list[ProductionOrder],
        position: LotPosition,
    ) -> None:
        # A number conflict is not replayable here, because the loaded
        # aggregates were already mutated, so it maps to a 409. Events are
        # staged before the fallible recompute, which must not swallow them.
        for saved_order in created_orders:
            await self._bus.publish(
                ProductionOrderCreated(
                    production_order_id=saved_order.id,
                    machine_id=saved_order.machine_id,
                    lot_position_id=position.id,
                    creator_id=actor.id,
                    machine_pool_id=saved_order.machine_pool_id,
                )
            )

    async def _recompute_schedule_after_commit(
        self, created_orders: list[ProductionOrder], position_id: int
    ) -> None:
        if created_orders:
            await recompute_schedule_after_commit(
                self._recompute,
                after=(
                    f"assigning position #{position_id}; "
                    f"the assignment itself is committed and its events are published."
                ),
            )
