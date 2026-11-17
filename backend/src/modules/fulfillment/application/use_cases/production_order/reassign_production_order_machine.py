"""
Moves a QUEUED (or PAUSED) production order to a different machine, to a
machine pool, to no machine at all (machine_id=None), or out of the
unassigned pool onto a real machine. Backs both a deliberate "assign a
machine/pool" action and a kanban drag between machine/pool columns; the
guards mirror reorder_production_orders.py's, since a cross-machine move is
really a queue-membership change, same family of operation as a same-machine
reorder: a pinned order can't move (403, InsufficientPermissionsError: a
genuine permission/lock precedent), and an order that is no longer QUEUED/
PAUSED (IN_PROGRESS, COMPLETED or CANCELED) can't move either (422,
ProductionOrderInvalidStatusTransitionError: a state conflict, not a
permission one).

Pool target semantics (pool-first planning): a machine target
(cmd.machine_id) resolves the order onto that machine while KEEPING
whatever machine_pool_id it already carries, mirroring how the Start
dialog resolves a pool-assigned order (machine_id set, machine_pool_id
kept as provenance). A pool target (cmd.machine_pool_id) clears
machine_id and validates the position against the pool's own derived
capability (assert_pool_capability_match). Neither given is the plain
"unassign" request: machine_id is cleared, machine_pool_id is left
exactly as it was. On an already-resolved order (machine_id set,
machine_pool_id also set) this deliberately reverts it back to
pool-assigned-unresolved rather than dropping the pool link too.

The target queue is locked first, then the order row through the request's
lock plan, and the guards run again on the order read under both locks; an
order that moved in between, so that its target queue is not the one
locked, is refused with ConcurrentModificationError
(queue_scope_locks.py). The moved order loses its planned window, so the
walk places it on its new queue even where a frozen window would otherwise
keep it.
"""

from src.modules.catalogue.domain.errors import ProductionMachineNotFoundError
from src.modules.fulfillment.application.dto.production_order_dto import ProductionOrderResult
from src.modules.fulfillment.application.dto.production_order_dto import (
    ReassignProductionOrderMachineCommand,
)
from src.modules.fulfillment.application.mappers.production_order_mapper import (
    ProductionOrderMapper,
)
from src.modules.fulfillment.application.services.lifecycle_loader import AggregateIds
from src.modules.fulfillment.application.services.lifecycle_lock_plan import LockPlan
from src.modules.fulfillment.application.services.planned_window import drop_planned_window
from src.modules.fulfillment.application.services.queue_scope_locks import QueueScope
from src.modules.fulfillment.application.services.queue_scope_locks import assert_queue_scope_held
from src.modules.fulfillment.application.services.queue_scope_locks import lock_queue_scopes_first
from src.modules.fulfillment.application.use_cases.production_schedule.recompute_machine_schedule import (
    RecomputeMachineSchedule,
)
from src.modules.fulfillment.domain.entities.production_order import ProductionOrder
from src.modules.fulfillment.domain.errors import LotPositionNotFoundError
from src.modules.fulfillment.domain.errors import MachinePoolNotFoundError
from src.modules.fulfillment.domain.errors import ProductionOrderInvalidStatusTransitionError
from src.modules.fulfillment.domain.errors import ProductionOrderNotFoundError
from src.modules.fulfillment.domain.services.production_order_rules import ProductionOrderRules
from src.modules.fulfillment.domain.services.production_order_rules import assert_capability_match
from src.modules.fulfillment.domain.services.production_order_rules import assert_machine_takes_work
from src.modules.fulfillment.domain.services.production_order_rules import (
    assert_pool_capability_match,
)
from src.modules.fulfillment.domain.value_objects.lifecycle_aggregate import LifecycleAggregate
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
from src.modules.fulfillment.ports.outbound.repositories.production_order_repository import (
    IProductionOrderRepository,
)
from src.modules.platform.application.services.lookup import found_or_raise
from src.modules.platform.application.services.schedule_recompute_port import (
    recompute_schedule_after_commit,
)
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.exceptions import InsufficientPermissionsError
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.ports.outbound.event_bus_port import IEventBus
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork
from src.shared_kernel.domain.services.changelog_service import append_changelog
from src.shared_kernel.domain.services.clock import now_utc


class ReassignProductionOrderMachine:
    def __init__(
        self,
        order_repo: IProductionOrderRepository,
        lot_repo: IProductionLotRepository,
        machine_repo: IProductionMachineRepository,
        *,
        event_bus: IEventBus,
        uow: IUnitOfWork,
        recompute_schedule: RecomputeMachineSchedule | None = None,
        pool_repo: IMachinePoolRepository | None = None,
        lock_plan: LockPlan,
    ) -> None:
        self._lock_plan = lock_plan
        self._orders = order_repo
        self._lots = lot_repo
        self._machines = machine_repo
        self._bus = event_bus
        self._uow = uow
        self._recompute = recompute_schedule
        self._pools = pool_repo

    async def execute(
        self,
        actor: User,
        production_order_id: int,
        cmd: ReassignProductionOrderMachineCommand,
    ) -> ProductionOrderResult:
        ProductionOrderRules.assert_can_assign(actor)
        order = await self._load(production_order_id)
        self._assert_movable(actor, order)
        scopes = await lock_queue_scopes_first(self._orders, [_target_scope(order, cmd)])
        await self._lock_plan.acquire(
            AggregateIds.of({LifecycleAggregate.PRODUCTION_ORDERS: [order.id]})
        )
        order = await self._load(production_order_id)
        self._assert_movable(actor, order)

        position = found_or_raise(
            await self._lots.get_position_by_id(order.lot_position_id),
            LotPositionNotFoundError,
            f"Position #{order.lot_position_id} not found.",
        )

        new_machine_id = cmd.machine_id
        new_machine_pool_id = cmd.machine_pool_id
        moved_from = _place(order)

        if new_machine_id is not None:
            machine = found_or_raise(
                await self._machines.get_by_id(new_machine_id),
                ProductionMachineNotFoundError,
                f"Machine #{new_machine_id} not found.",
            )
            assert_machine_takes_work(machine)
            assert_capability_match(machine, position.steps)
            note = f"Reassigned to machine #{new_machine_id}."
            order.machine_id = new_machine_id
            # machine_pool_id intentionally left untouched: resolving to a
            # concrete machine keeps whatever pool provenance the order
            # already carried (mirrors StartProductionOrder).
        elif new_machine_pool_id is not None:
            if self._pools is None:
                raise MachinePoolNotFoundError(f"Machine pool #{new_machine_pool_id} not found.")
            pool = found_or_raise(
                await self._pools.get_by_id(new_machine_pool_id),
                MachinePoolNotFoundError,
                f"Machine pool #{new_machine_pool_id} not found.",
            )
            assert_pool_capability_match(pool, position.steps)
            note = f"Reassigned to machine pool #{new_machine_pool_id}."
            order.machine_id = None
            order.machine_pool_id = new_machine_pool_id
        else:
            note = "Reassigned to the unassigned queue."
            order.machine_id = None
            # machine_pool_id left as-is: reverts an already-resolved order
            # back to pool-assigned-unresolved if it had one, otherwise
            # stays fully unassigned; see this module's docstring.

        now = now_utc()
        # Serialized against a concurrent assign/reassign/reorder landing in
        # the same target queue by the scope lock taken before the row lock:
        # next_queue_sequence is an unlocked read-then-increment (see
        # IProductionOrderRepository.lock_queue_scope).
        assert_queue_scope_held(scopes, order.machine_id, order.machine_pool_id, order.id)
        order.queue_sequence = await self._orders.next_queue_sequence(
            order.machine_id, order.machine_pool_id
        )
        drop_planned_window(order)
        # The changelog names where the order came from as well, so a paused
        # order's move between machines stays traceable next to the
        # completions booked on each.
        note = f"{note[:-1]} from {moved_from}."
        if order.status == ProductionOrderStatus.PAUSED:
            note += f" Paused after {order.quantity_completed:g} completed piece(s)."
        order.changed = now
        order.changes = append_changelog(order.changes, actor.full_name, note)
        saved_order = await self._orders.save(order)

        # A machine, a pool and a queue place feed no lifecycle status, so
        # nothing is reconciled.
        await self._uow.commit()

        # A cross-queue move changes two queues at once (the order's old
        # machine and its new one, either of which may be the unassigned
        # bucket). execute_all() re-walks every machine, pool, manual and
        # unassigned bucket in one pass regardless, so a single call already
        # covers both ends.
        await recompute_schedule_after_commit(
            self._recompute,
            after=(
                f"reassigning production order "
                f"#{production_order_id}; the reassignment itself is committed "
                f"and its events are published."
            ),
        )

        log.info(f"Production order #{production_order_id} - {note}")
        return ProductionOrderMapper.to_result(saved_order)

    async def _load(self, production_order_id: int) -> ProductionOrder:
        order = await self._orders.get_by_id(production_order_id)
        if not order:
            raise ProductionOrderNotFoundError(
                f"Production order #{production_order_id} not found."
            )
        return order

    @staticmethod
    def _assert_movable(actor: User, order: ProductionOrder) -> None:
        ProductionOrderRules.assert_can_update(actor, order)
        if order.pinned:
            raise InsufficientPermissionsError(
                f"Production order #{order.id} is pinned and cannot be reassigned."
            )
        if order.status in (
            ProductionOrderStatus.IN_PROGRESS,
            ProductionOrderStatus.COMPLETED,
            ProductionOrderStatus.CANCELED,
        ):
            raise ProductionOrderInvalidStatusTransitionError(
                f"Production order #{order.id} is {order.status.value} and cannot be reassigned."
            )


def _place(order: ProductionOrder) -> str:
    """Where the order is queued, as a changelog line names it."""
    if order.machine_id is not None:
        return f"machine #{order.machine_id}"
    if order.machine_pool_id is not None:
        return f"machine pool #{order.machine_pool_id}"
    return "the unassigned queue"


def _target_scope(order: ProductionOrder, cmd: ReassignProductionOrderMachineCommand) -> QueueScope:
    """The queue the order lands in, as execute resolves it."""
    if cmd.machine_id is not None:
        return (cmd.machine_id, order.machine_pool_id)
    if cmd.machine_pool_id is not None:
        return (None, cmd.machine_pool_id)
    return (None, order.machine_pool_id)
