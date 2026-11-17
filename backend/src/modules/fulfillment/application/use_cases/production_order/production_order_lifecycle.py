"""Start, pause and cancel of production orders, always explicit and never
implied by a queue reorder.

Each use case records the facts and intents of its action, and the lifecycle
reconciler derives the order's status from them: a start sets actual_start,
which only the first start does, a pause opens a manual interruption, a
resume closes it, and a cancel stamps canceled_at and closes every
interruption still open. The net work time is therefore the span from the
first start to the end minus the closed interruptions. The production order
intent table (lifecycle/intents.py) decides which action the order's state
allows; the checks of the machine, the lot and the upstream input that
follow it name what is missing. The order's lot and then the order are
locked through the request's lock plan before the checks read them; a start
of a pool-assigned order takes the named machine's queue lock before them
(queue_scope_locks.py).

The operator must always be resolved. Only completions have an operator
audit table; start and resume record the operator in the changelog and in
started_operator_id.

The reconciler also derives the kind and status of the order's position, the
status of its lot and those of the lot's made demands. When the position's
kind changed, which decides whether it counts towards the project's time
budgets, the budgets are recomputed after the commit.
"""

from datetime import datetime

from src.modules.catalogue.domain.errors import MachineCapabilityMismatchError
from src.modules.catalogue.domain.errors import ProductionMachineNotFoundError
from src.modules.catalogue.domain.value_objects.step_role import StepRole
from src.modules.fulfillment.application.dto.production_order_dto import (
    CancelProductionOrderCommand,
)
from src.modules.fulfillment.application.dto.production_order_dto import PauseProductionOrderCommand
from src.modules.fulfillment.application.dto.production_order_dto import ProductionOrderResult
from src.modules.fulfillment.application.dto.production_order_dto import StartProductionOrderCommand
from src.modules.fulfillment.application.mappers.production_order_mapper import (
    ProductionOrderMapper,
)
from src.modules.fulfillment.application.services.lifecycle_reconciler import LifecycleReconciler
from src.modules.fulfillment.application.services.lifecycle_reconciler import ReconcileResult
from src.modules.fulfillment.application.services.production_order_interruptions import (
    close_open_interruptions,
)
from src.modules.fulfillment.application.services.queue_scope_locks import QueueScope
from src.modules.fulfillment.application.services.queue_scope_locks import assert_queue_scope_held
from src.modules.fulfillment.application.services.queue_scope_locks import lock_queue_scopes_first
from src.modules.fulfillment.application.services.time_budget_propagation import BudgetOrders
from src.modules.fulfillment.application.services.time_budget_propagation import budget_order_locks
from src.modules.fulfillment.application.services.time_budget_propagation import (
    recompute_project_time_budgets,
)
from src.modules.fulfillment.application.use_cases.production_order._locks import lock_lot_and_order
from src.modules.fulfillment.domain.entities.lot_position import LotPosition
from src.modules.fulfillment.domain.entities.production_lot import ProductionLot
from src.modules.fulfillment.domain.entities.production_order import ProductionOrder
from src.modules.fulfillment.domain.entities.production_order_interruption import (
    ProductionOrderInterruption,
)
from src.modules.fulfillment.domain.errors import LotPositionNotFoundError
from src.modules.fulfillment.domain.errors import MachinePoolNotFoundError
from src.modules.fulfillment.domain.errors import ProductionOrderInvalidStatusTransitionError
from src.modules.fulfillment.domain.errors import ProductionOrderNoMachineAssignedError
from src.modules.fulfillment.domain.errors import ProductionOrderNotFoundError
from src.modules.fulfillment.domain.events.production_order_events import ProductionOrderPaused
from src.modules.fulfillment.domain.events.production_order_events import ProductionOrderResumed
from src.modules.fulfillment.domain.events.production_order_events import ProductionOrderStarted
from src.modules.fulfillment.domain.services.lifecycle.stored import LifecycleField
from src.modules.fulfillment.domain.services.lot_event_service import build_lot_event
from src.modules.fulfillment.domain.services.lot_rules import assert_position_has_available_input
from src.modules.fulfillment.domain.services.production_order_rules import ProductionOrderRules
from src.modules.fulfillment.domain.services.production_order_rules import assert_capability_match
from src.modules.fulfillment.domain.services.production_order_rules import assert_machine_takes_work
from src.modules.fulfillment.domain.services.production_order_rules import (
    assert_production_order_action,
)
from src.modules.fulfillment.domain.services.production_order_rules import position_is_manual
from src.modules.fulfillment.domain.services.production_order_rules import resolve_operator_id
from src.modules.fulfillment.domain.value_objects.interruption_reason import InterruptionReason
from src.modules.fulfillment.domain.value_objects.lifecycle_aggregate import LifecycleAggregate
from src.modules.fulfillment.domain.value_objects.lot_event_type import LotEventType
from src.modules.fulfillment.domain.value_objects.lot_status import TERMINAL_LOT_STATUSES
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionKind
from src.modules.fulfillment.domain.value_objects.lot_status import LotStatus
from src.modules.fulfillment.domain.value_objects.production_status import ProductionOrderStatus
from src.modules.fulfillment.ports.outbound.repositories.machine_pool_repository import (
    IMachinePoolRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.production_lot_repository import (
    IProductionLotRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.production_machine_repository import (
    IProductionMachineRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.production_order_interruption_repository import (
    IProductionOrderInterruptionRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.production_order_repository import (
    IProductionOrderRepository,
)
from src.modules.platform.application.services.lookup import found_or_raise
from src.modules.platform.application.services.schedule_recompute_port import ScheduleRecompute
from src.modules.platform.application.services.schedule_recompute_port import (
    recompute_schedule_after_commit,
)
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.exceptions import InsufficientPermissionsError
from src.modules.platform.domain.services.edit_version import assert_edit_version
from src.modules.platform.domain.services.edit_version import bump_edit_version
from src.modules.platform.domain.value_objects.permission import Permission
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.ports.outbound.event_bus_port import IEventBus
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork
from src.modules.workspace.ports.outbound.workspace_queries import IProjectQueries
from src.shared_kernel.domain.services.changelog_service import append_changelog
from src.shared_kernel.domain.services.clock import now_utc
from src.shared_kernel.domain.value_objects.lifecycle_action import LifecycleAction


class _ProductionOrderLifecycleBase:
    def __init__(
        self,
        order_repo: IProductionOrderRepository,
        lot_repo: IProductionLotRepository,
        *,
        event_bus: IEventBus,
        uow: IUnitOfWork,
        reconciler: LifecycleReconciler,
        interruption_repo: IProductionOrderInterruptionRepository,
        project_repo: IProjectQueries | None = None,
        machine_repo: IProductionMachineRepository | None = None,
        pool_repo: IMachinePoolRepository | None = None,
        recompute_schedule: ScheduleRecompute | None = None,
    ) -> None:
        self._recompute = recompute_schedule
        self._orders = order_repo
        self._lots = lot_repo
        self._bus = event_bus
        self._uow = uow
        self._reconciler = reconciler
        self._interruptions = interruption_repo
        self._projects = project_repo
        self._machines = machine_repo
        self._pools = pool_repo

    async def _load(self, production_order_id: int) -> ProductionOrder:
        order = await self._orders.get_by_id(production_order_id)
        if not order:
            raise ProductionOrderNotFoundError(
                f"Production order #{production_order_id} not found."
            )
        return order

    async def _lock(
        self, order: ProductionOrder
    ) -> tuple[ProductionLot, ProductionOrder, LotPosition]:
        """Locks the order's lot, then the order, and reads both again
        (_locks.py). The checks and writes after it use only what it
        returns."""
        position = found_or_raise(
            await self._lots.get_position_by_id(order.lot_position_id),
            LotPositionNotFoundError,
            f"Position #{order.lot_position_id} not found.",
        )
        return await lock_lot_and_order(
            self._reconciler, self._lots, self._orders, position, order.id
        )

    async def _reconciled(self, production_order_id: int) -> ProductionOrder:
        """The order as the reconciler stored it, for the response."""
        return await self._load(production_order_id)

    @staticmethod
    def _assert_lot_startable(lot: ProductionLot, production_order_id: int) -> None:
        """Hold leaves queued orders untouched, so this keeps them from
        starting on a held lot. A stray live order under a terminal lot is
        never startable either."""
        if lot.status == LotStatus.ON_HOLD:
            raise ProductionOrderInvalidStatusTransitionError(
                f"Production order #{production_order_id} belongs to lot {lot.lot_number!r}, "
                f"which is on hold; resume the lot first."
            )
        if lot.status in TERMINAL_LOT_STATUSES:
            raise ProductionOrderInvalidStatusTransitionError(
                f"Production order #{production_order_id} belongs to lot {lot.lot_number!r}, "
                f"which is {lot.status.value} and can no longer be started."
            )

    @staticmethod
    def _assert_can_operate_inspection(actor: User, position: LotPosition) -> None:
        """Running an inspection order is the QA work itself, so it also needs
        WRITE_INSPECTIONS, the same gate as recording the verdict."""
        if not any(s.role == StepRole.INSPECTION for s in position.steps):
            return
        if not actor.has_permission(Permission.WRITE_INSPECTIONS):
            raise InsufficientPermissionsError(
                f"User #{actor.id} ({actor.full_name}) cannot start an inspection; "
                "write:inspections is required."
            )

    async def _assert_upstream_available(self, lot: ProductionLot, position: LotPosition) -> None:
        """Starting or resuming must not get ahead of the upstream. For
        sequence 1 the arrived raw material counts, 0.0 without a linked
        demand, so step 1 never starts before its material has arrived."""
        raw_material_arrived = None
        if (
            position.sequence == 1
            and position.kind in (LotPositionKind.INTERNAL, LotPositionKind.MIXED)
            and not lot.is_alteration
        ):
            raw_material_arrived = (
                await self._lots.get_raw_material_arrived_quantity(lot.input_demand_id)
                if lot.input_demand_id is not None
                else 0.0
            )
        assert_position_has_available_input(
            position, lot.positions, lot.quantity, raw_material_arrived
        )

    async def _after_run(self, result: ReconcileResult, lot: ProductionLot) -> int | None:
        """The project whose time budgets the caller recomputes after its
        commit, set only when the run changed a position's kind, which
        decides whether the position counts towards the budgets."""
        kind_changed = any(
            c.aggregate is LifecycleAggregate.LOT_POSITIONS and c.field is LifecycleField.KIND
            for c in result.changes
        )
        return lot.project_id if self._projects is not None and kind_changed else None

    async def _recompute_time_budget_if_needed(
        self,
        project_id_to_recompute: int | None,
        production_order_id: int,
        action_ing: str,
        action_noun: str,
    ) -> None:
        """Best-effort time-budget recompute in its own transaction. A failure
        must never look like the already committed transition failed. The
        transaction locks the project's queued and paused orders, whose
        duration the recompute may snapshot again, before the time budget
        lock, and a changed duration walks the schedule again."""
        if project_id_to_recompute is None:
            return
        assert self._projects is not None
        try:
            # The transition's commit released its locks.
            self._reconciler.transaction_ended()
            lock_plan = self._reconciler.lock_plan
            await lock_plan.acquire(
                await budget_order_locks([project_id_to_recompute], self._lots, self._orders)
            )
            touched_machine_ids = await recompute_project_time_budgets(
                project_id_to_recompute,
                self._projects,
                self._lots,
                BudgetOrders(self._orders, lock_plan),
            )
            await self._uow.commit()
        except Exception:
            await self._uow.rollback()
            log.exception(
                f"Project time-budget recompute failed after {action_ing} production "
                f"order #{production_order_id}; the {action_noun} itself is committed and "
                f"its events are published."
            )
            return
        if touched_machine_ids:
            await recompute_schedule_after_commit(
                self._recompute,
                after=f"recomputing the time budgets of project #{project_id_to_recompute}; "
                "the new budgets are committed.",
            )


def _start_scopes(order: ProductionOrder, cmd: StartProductionOrderCommand) -> list[QueueScope]:
    """The queue a start works in, read before the locks: a pool-assigned
    order's named pool member, whose queue it draws its place from, or an
    assigned order's own machine, whose queue Auto-Plan or a reorder may be
    rewriting under that queue's lock."""
    if order.machine_id is not None:
        return [(order.machine_id, order.machine_pool_id)]
    if order.machine_pool_id is not None and cmd.machine_id:
        return [(cmd.machine_id, order.machine_pool_id)]
    return []


def _start_action(order: ProductionOrder) -> LifecycleAction:
    """Start continues a paused order, which is a resume, and starts any
    other order, which the intent table refuses unless it is queued."""
    if order.status == ProductionOrderStatus.PAUSED:
        return LifecycleAction.RESUME
    return LifecycleAction.START


class StartProductionOrder(_ProductionOrderLifecycleBase):
    async def execute(
        self, actor: User, production_order_id: int, cmd: StartProductionOrderCommand
    ) -> ProductionOrderResult:
        # Checked before any row lock, so a request that cannot succeed fails
        # early. Every check runs again on the locked rows below.
        order = await self._load(production_order_id)
        ProductionOrderRules.assert_can_update(actor, order)
        assert_production_order_action(_start_action(order), order, actor)

        scopes = await lock_queue_scopes_first(self._orders, _start_scopes(order, cmd))
        lot, order, position = await self._lock(order)
        if order.machine_id is not None:
            assert_queue_scope_held(scopes, order.machine_id, order.machine_pool_id, order.id)
        ProductionOrderRules.assert_can_update(actor, order)
        action = _start_action(order)
        assert_production_order_action(action, order, actor)
        machine_id = await self._resolve_start_machine(order, position, cmd, scopes)
        self._assert_can_operate_inspection(actor, position)
        self._assert_lot_startable(lot, order.id)
        await self._assert_upstream_available(lot, position)

        operator_id = resolve_operator_id(actor, cmd.operator_id)
        now = now_utc()
        resuming = action is LifecycleAction.RESUME
        await self._apply_start(order, actor, operator_id, now, resuming)
        result = await self._reconciler.run(actor, now)
        project_id_to_recompute = await self._after_run(result, lot)
        await self._lots.record_event(
            build_lot_event(
                lot.id,
                actor,
                LotEventType.ORDER_STARTED,
                "order",
                f"Production order #{order.id} started (operator #{operator_id}).",
                entity_id=order.id,
            )
        )
        await self._publish_start_events(order, machine_id, actor, resuming)

        await self._uow.commit()

        # A running order anchors its queue at its start.
        await recompute_schedule_after_commit(
            self._recompute,
            after=f"starting production order #{production_order_id}; the start is committed.",
        )
        await self._recompute_time_budget_if_needed(
            project_id_to_recompute, production_order_id, "starting", "start"
        )

        log.info(f"Started production order #{production_order_id}.")
        return ProductionOrderMapper.to_result(await self._reconciled(production_order_id))

    async def _resolve_start_machine(
        self,
        order: ProductionOrder,
        position: LotPosition,
        cmd: StartProductionOrderCommand,
        scopes: frozenset[QueueScope],
    ) -> int | None:
        """The machine this start runs on: the order's own, none for a manual
        position, or the pool member named in the command."""
        if order.machine_id is not None:
            if cmd.machine_id is not None:
                raise ProductionOrderInvalidStatusTransitionError(
                    f"Production order #{order.id} already has a machine assigned; "
                    f"machine_id must be omitted."
                )
            return order.machine_id

        if order.machine_pool_id is None:
            if not position_is_manual(position.steps):
                raise ProductionOrderNoMachineAssignedError(
                    f"Production order #{order.id} has no machine assigned; assign one "
                    f"before starting it."
                )
            return None

        await self._resolve_pool_assigned_machine(order, position, cmd, scopes)
        return order.machine_id

    async def _resolve_pool_assigned_machine(
        self,
        order: ProductionOrder,
        position: LotPosition,
        cmd: StartProductionOrderCommand,
        scopes: frozenset[QueueScope],
    ) -> None:
        """On start the user names the pool member. It is validated against
        membership and capability and written with a fresh queue_sequence
        from the machine's scope."""
        assert order.machine_pool_id is not None
        if cmd.machine_id is None:
            raise ProductionOrderNoMachineAssignedError(
                f"Production order #{order.id} is assigned to machine pool "
                f"#{order.machine_pool_id}; pick a machine from the pool to start it."
            )
        if self._pools is None or self._machines is None:
            raise ProductionOrderNoMachineAssignedError(
                f"Production order #{order.id} cannot resolve its machine pool assignment."
            )
        pool = found_or_raise(
            await self._pools.get_by_id(order.machine_pool_id),
            MachinePoolNotFoundError,
            f"Machine pool #{order.machine_pool_id} not found.",
        )
        if cmd.machine_id not in pool.machine_ids:
            raise MachineCapabilityMismatchError(
                f"Machine #{cmd.machine_id} is not a member of machine pool "
                f"#{pool.id} ({pool.name})."
            )
        machine = found_or_raise(
            await self._machines.get_by_id(cmd.machine_id),
            ProductionMachineNotFoundError,
            f"Machine #{cmd.machine_id} not found.",
        )
        assert_machine_takes_work(machine)
        assert_capability_match(machine, position.steps)
        order.machine_id = cmd.machine_id
        # The pool-scope sequence may collide on the machine, so draw a new
        # one under the machine's scope lock, taken before the row locks.
        assert_queue_scope_held(scopes, order.machine_id, order.machine_pool_id, order.id)
        order.queue_sequence = await self._orders.next_queue_sequence(
            order.machine_id, order.machine_pool_id
        )

    async def _apply_start(
        self,
        order: ProductionOrder,
        actor: User,
        operator_id: int,
        now: datetime,
        resuming: bool,
    ) -> None:
        """Records the start of the order, or the resume of its pause.
        actual_start keeps the first start, because the net work time
        subtracts the closed interruptions from the span since then; a
        resume closes the operator's own pause."""
        order.actual_start = order.actual_start or now
        order.changed = now
        order.started_operator_id = operator_id
        # Frozen at the first start as the schedule-adherence baseline.
        if order.planned_end_at_start is None:
            order.planned_end_at_start = order.planned_end
        order.changes = append_changelog(
            order.changes, actor.full_name, f"Started (operator #{operator_id})."
        )
        await self._orders.save(order)
        if resuming:
            await self._interruptions.close_open(
                order.id, now, actor.id, reason=InterruptionReason.MANUAL
            )

    async def _publish_start_events(
        self,
        order: ProductionOrder,
        machine_id: int | None,
        actor: User,
        resuming: bool,
    ) -> None:
        """Staged before the fallible time-budget recompute, so its failure
        cannot swallow the events of a committed start."""
        await self._bus.publish(
            ProductionOrderStarted(
                production_order_id=order.id,
                machine_id=machine_id,
                actor_id=actor.id,
                machine_pool_id=order.machine_pool_id,
            )
        )
        if resuming:
            await self._bus.publish(
                ProductionOrderResumed(
                    production_order_id=order.id,
                    actor_id=actor.id,
                    machine_id=machine_id,
                )
            )


class PauseProductionOrder(_ProductionOrderLifecycleBase):
    """Pauses a running order by opening a manual interruption, which its
    derived status reads as PAUSED, and records a lot timeline event. A hold
    of the order's lot opens an interruption of its own (HoldLot)."""

    async def execute(
        self, actor: User, production_order_id: int, cmd: PauseProductionOrderCommand
    ) -> ProductionOrderResult:
        order = await self._load(production_order_id)
        ProductionOrderRules.assert_can_update(actor, order)
        assert_production_order_action(LifecycleAction.PAUSE, order, actor)

        lot, order, _position = await self._lock(order)
        ProductionOrderRules.assert_can_update(actor, order)
        assert_production_order_action(LifecycleAction.PAUSE, order, actor)

        operator_id = resolve_operator_id(actor, cmd.operator_id)

        now = now_utc()
        note = f" Reason: {cmd.reason}" if cmd.reason else ""
        order.changed = now
        order.changes = append_changelog(
            order.changes, actor.full_name, f"Paused (operator #{operator_id}).{note}"
        )
        await self._orders.save(order)
        await self._interruptions.add(
            ProductionOrderInterruption(
                id=0,
                production_order_id=order.id,
                paused_at=now,
                resumed_at=None,
                paused_by_id=actor.id,
                resumed_by_id=None,
                created=now,
                reason=InterruptionReason.MANUAL,
                paused_operator_id=operator_id,
            )
        )
        result = await self._reconciler.run(actor, now)
        project_id_to_recompute = await self._after_run(result, lot)
        await self._lots.record_event(
            build_lot_event(
                lot.id,
                actor,
                LotEventType.ORDER_PAUSED,
                "order",
                f"Production order #{order.id} paused (operator #{operator_id}).{note}",
                entity_id=order.id,
            )
        )
        # Staged before the fallible time-budget recompute.
        await self._bus.publish(
            ProductionOrderPaused(production_order_id=order.id, actor_id=actor.id)
        )

        await self._uow.commit()

        # A paused order consumes no capacity, so the orders after it move up.
        await recompute_schedule_after_commit(
            self._recompute,
            after=f"pausing production order #{production_order_id}; the pause is committed.",
        )
        await self._recompute_time_budget_if_needed(
            project_id_to_recompute, production_order_id, "pausing", "pause"
        )

        log.info(f"Paused production order #{production_order_id}.")
        return ProductionOrderMapper.to_result(await self._reconciled(production_order_id))


class CancelProductionOrder(_ProductionOrderLifecycleBase):
    """Cancels an order by stamping canceled_at, which its derived status
    reads as CANCELED, and closes every interruption still open. The
    schedule adherence baseline, planned_end_at_start, stays as it was; the
    reconciler publishes ProductionOrderCanceled."""

    async def execute(
        self, actor: User, production_order_id: int, cmd: CancelProductionOrderCommand
    ) -> ProductionOrderResult:
        order = await self._load(production_order_id)
        self._assert_can_cancel(actor, order)

        lot, order, _position = await self._lock(order)
        self._assert_can_cancel(actor, order)
        assert_edit_version(order, cmd.expected_edit_version, what=f"Production order #{order.id}")

        now = now_utc()
        note = f" Reason: {cmd.reason}" if cmd.reason else ""
        bump_edit_version(order)
        order.canceled_at = now
        order.changed = now
        order.changes = append_changelog(order.changes, actor.full_name, f"Canceled.{note}")
        await self._orders.save(order)
        await close_open_interruptions(self._interruptions, order.id, now, actor.id)
        result = await self._reconciler.run(actor, now)
        project_id_to_recompute = await self._after_run(result, lot)
        await self._lots.record_event(
            build_lot_event(
                lot.id,
                actor,
                LotEventType.ORDER_CANCELED,
                "order",
                f"Production order #{order.id} canceled.{note}",
                entity_id=order.id,
            )
        )

        await self._uow.commit()

        # A canceled order frees its place in the queue.
        await recompute_schedule_after_commit(
            self._recompute,
            after=f"canceling production order #{production_order_id}; the cancel is committed.",
        )
        await self._recompute_time_budget_if_needed(
            project_id_to_recompute, production_order_id, "canceling", "cancel"
        )

        log.info(f"Canceled production order #{production_order_id}.")
        return ProductionOrderMapper.to_result(await self._reconciled(production_order_id))

    @staticmethod
    def _assert_can_cancel(actor: User, order: ProductionOrder) -> None:
        ProductionOrderRules.assert_can_cancel(actor, order)
        assert_production_order_action(LifecycleAction.CANCEL, order, actor)
