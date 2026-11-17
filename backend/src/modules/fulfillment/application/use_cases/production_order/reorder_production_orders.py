"""Reorders one queue (a machine, a pool, or the bucket without either) by
rewriting queue_sequence only, then recomputes dates. Pinned orders (403)
and orders that are no longer QUEUED or PAUSED (422) cannot move, and
duplicate ids are rejected.

queue_sequence is unique per scope among live orders, and anchors left
out of the request keep their values anywhere in the sequence. The
touched orders therefore get a permutation of the values they already
held, which cannot collide with an anchor. The rewrite first shifts them
to negative values, because the unique indexes are not deferrable. A moved
order loses its planned window, so the walk places it at its new place even
where a frozen window would otherwise keep it.

The queue's lock comes first, then the moved orders' rows through the
request's lock plan, the order every writer of a queue follows
(queue_scope_locks.py).
"""

from src.modules.fulfillment.application.dto.production_order_dto import ProductionOrderResult
from src.modules.fulfillment.application.dto.production_order_dto import (
    ReorderProductionOrdersCommand,
)
from src.modules.fulfillment.application.mappers.production_order_mapper import (
    ProductionOrderMapper,
)
from src.modules.fulfillment.application.services.lifecycle_loader import AggregateIds
from src.modules.fulfillment.application.services.lifecycle_lock_plan import LockPlan
from src.modules.fulfillment.application.services.planned_window import drop_planned_window
from src.modules.fulfillment.application.use_cases.production_schedule.recompute_machine_schedule import (
    RecomputeMachineSchedule,
)
from src.modules.fulfillment.domain.entities.production_order import ProductionOrder
from src.modules.fulfillment.domain.errors import ProductionOrderInvalidStatusTransitionError
from src.modules.fulfillment.domain.errors import ProductionOrderNotFoundError
from src.modules.fulfillment.domain.errors import ProductionOrderReorderInvalidError
from src.modules.fulfillment.domain.services.production_order_rules import ProductionOrderRules
from src.modules.fulfillment.domain.value_objects.lifecycle_aggregate import LifecycleAggregate
from src.modules.fulfillment.domain.value_objects.production_status import (
    TERMINAL_PRODUCTION_ORDER_STATUSES,
)
from src.modules.fulfillment.domain.value_objects.production_status import ProductionOrderStatus
from src.modules.fulfillment.ports.outbound.repositories.production_order_repository import (
    IProductionOrderRepository,
)
from src.modules.platform.application.services.schedule_recompute_port import (
    recompute_schedule_after_commit,
)
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.exceptions import InsufficientPermissionsError
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.ports.outbound.event_bus_port import IEventBus
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork


class ReorderProductionOrders:
    def __init__(
        self,
        order_repo: IProductionOrderRepository,
        recompute_schedule: RecomputeMachineSchedule | None = None,
        *,
        event_bus: IEventBus,
        uow: IUnitOfWork,
        lock_plan: LockPlan,
    ) -> None:
        self._lock_plan = lock_plan
        self._orders = order_repo
        self._recompute = recompute_schedule
        self._bus = event_bus
        self._uow = uow

    async def _scope_orders(
        self, machine_id: int | None, machine_pool_id: int | None
    ) -> tuple[str, list[ProductionOrder]]:
        """The live orders of the queue being reordered and a label for error
        messages."""
        if machine_id is not None:
            return f"machine #{machine_id}", await self._orders.get_live_by_machine_ids(
                [machine_id]
            )
        machine_less = await self._orders.get_live_by_machine_ids([None])
        if machine_pool_id is not None:
            return (
                f"machine pool #{machine_pool_id}",
                [o for o in machine_less if o.machine_pool_id == machine_pool_id],
            )
        return (
            "the unassigned queue",
            [o for o in machine_less if o.machine_pool_id is None],
        )

    async def execute(
        self,
        actor: User,
        machine_id: int | None,
        cmd: ReorderProductionOrdersCommand,
        machine_pool_id: int | None = None,
    ) -> list[ProductionOrderResult]:
        ProductionOrderRules.assert_can_assign(actor)
        # Locked before reading, so a concurrent assignment cannot shift the
        # scope underneath the rewrite.
        await self._orders.lock_queue_scope(machine_id, machine_pool_id)
        machine_label, scope_orders = await self._scope_orders(machine_id, machine_pool_id)
        # The rows the rewrite moves are locked after the queue, through the
        # request's lock plan, and the queue is read again, so the status and
        # pin checks below see what a concurrent start or pin committed.
        listed = set(cmd.ordered_production_order_ids)
        await self._lock_plan.acquire(
            AggregateIds.of(
                {
                    LifecycleAggregate.PRODUCTION_ORDERS: [
                        o.id for o in scope_orders if o.id in listed
                    ]
                }
            )
        )
        machine_label, scope_orders = await self._scope_orders(machine_id, machine_pool_id)

        # A duplicate id would assign a sequence ambiguously.
        ordered_ids = cmd.ordered_production_order_ids
        if len(set(ordered_ids)) != len(ordered_ids):
            raise ProductionOrderReorderInvalidError(
                "The ordered production order id list contains duplicate ids."
            )

        existing = {o.id: o for o in scope_orders}
        missing = set(ordered_ids) - set(existing.keys())
        if missing:
            # A completed or canceled order of the queue is no longer read
            # with it, but is refused for its status rather than as missing.
            for ended in await self._orders.get_by_ids(sorted(missing)):
                if ended.status in TERMINAL_PRODUCTION_ORDER_STATUSES:
                    raise ProductionOrderInvalidStatusTransitionError(
                        f"Production order #{ended.id} is {ended.status.value} and cannot be reordered."
                    )
            raise ProductionOrderNotFoundError(
                f"Production order(s) {missing} not found on {machine_label}."
            )

        for order_id in ordered_ids:
            order = existing[order_id]
            if order.pinned:
                raise InsufficientPermissionsError(
                    f"Production order #{order_id} is pinned and cannot be reordered."
                )
            if order.status == ProductionOrderStatus.IN_PROGRESS:
                raise ProductionOrderInvalidStatusTransitionError(
                    f"Production order #{order_id} is {order.status.value} and cannot be reordered."
                )

        # The touched orders' own values, permuted (module docstring).
        final_values = sorted(existing[order_id].queue_sequence for order_id in ordered_ids)

        # Shift to negative values first (module docstring).
        await self._orders.shift_queue_sequence(ordered_ids)

        saved_orders = []
        for sequence, order_id in zip(final_values, ordered_ids, strict=True):
            order = existing[order_id]
            order.queue_sequence = sequence
            drop_planned_window(order)
            saved_orders.append(await self._orders.save(order))

        await self._uow.commit()

        await recompute_schedule_after_commit(
            self._recompute,
            after=(
                f"reordering production orders on {machine_label}; the new order itself "
                f"is committed."
            ),
        )

        log.info(
            f"Reordered {len(cmd.ordered_production_order_ids)} "
            f"production order(s) on {machine_label}."
        )
        return [ProductionOrderMapper.to_result(o) for o in saved_orders]
