"""
Removes a single order item and deallocates its demands, lets the lifecycle reconciler derive
the order's status without the line, the statuses of the demands that lost an allocation, and
the kind and status of its linked lot position for a MADE line, and optionally recomputes the
machine schedule.
"""

from src.modules.fulfillment.application.services.allocation_release import deallocate_order_item
from src.modules.fulfillment.application.services.allocation_release import (
    deallocate_source_item_order_item,
)
from src.modules.fulfillment.application.services.lifecycle_reconciler import LifecycleReconciler
from src.modules.fulfillment.application.services.lot_provisions import assert_no_provisions
from src.modules.fulfillment.application.use_cases.order._lines import lots_of_made_lines
from src.modules.fulfillment.application.use_cases.production_schedule.recompute_machine_schedule import (
    RecomputeMachineSchedule,
)
from src.modules.fulfillment.domain.entities.order_item import OrderItem
from src.modules.fulfillment.domain.errors import OrderItemNotFoundError
from src.modules.fulfillment.domain.errors import OrderNotFoundError
from src.modules.fulfillment.domain.services.order_rules import OrderRules
from src.modules.fulfillment.domain.value_objects.lifecycle_aggregate import LifecycleAggregate
from src.modules.fulfillment.ports.outbound.repositories.bought_item_demand_repository import (
    IBoughtItemAllocationRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.order_repository import (
    IOrderItemRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.order_repository import IOrderRepository
from src.modules.fulfillment.ports.outbound.repositories.production_lot_repository import (
    IProductionLotRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.source_item_demand_repository import (
    ISourceItemAllocationRepository,
)
from src.modules.platform.application.services.lookup import found_or_raise
from src.modules.platform.application.services.schedule_recompute_port import (
    recompute_schedule_after_commit,
)
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.services.edit_version import assert_edit_version
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork
from src.shared_kernel.domain.services.changelog_service import append_changelog
from src.shared_kernel.domain.services.clock import now_utc


class RemoveOrderItem:
    """
    Removes a single order item from an order.
    Only a PENDING or REQUESTED line is removed; an ORDERED line is canceled
    instead (cancel_order_item.py), and a canceled, partially delivered or
    delivered line stays as the record of what happened to it.
    A client sends the edit version of the line it showed, so a line edited
    since answers 409. Deallocates all allocations pointing at this item. The lifecycle
    reconciler derives the order's status from the lines that remain, the
    statuses of the demands that lost an allocation and, for a MADE line,
    the kind and status of the linked LotPosition without it.
    """

    def __init__(
        self,
        order_repo: IOrderRepository,
        order_item_repo: IOrderItemRepository,
        allocation_repo: IBoughtItemAllocationRepository,
        recompute_schedule: RecomputeMachineSchedule | None = None,
        *,
        uow: IUnitOfWork,
        reconciler: LifecycleReconciler,
        source_item_allocation_repo: ISourceItemAllocationRepository | None = None,
        lot_repo: IProductionLotRepository | None = None,
    ) -> None:
        self._orders = order_repo
        self._order_items = order_item_repo
        self._allocations = allocation_repo
        self._recompute = recompute_schedule
        self._uow = uow
        self._reconciler = reconciler
        self._source_item_allocations = source_item_allocation_repo
        self._lots = lot_repo

    async def execute(
        self,
        actor: User,
        order_id: int,
        order_item_id: int,
        expected_edit_version: int | None = None,
    ) -> None:
        order = found_or_raise(
            await self._orders.get_by_id(order_id),
            OrderNotFoundError,
            f"Order #{order_id} not found.",
        )
        item = await self._item_of(order_id, order_item_id)

        # The lot of a MADE line first, because the reconciler writes its
        # position.
        self._reconciler.touch_order_items([order_item_id])
        await self._reconciler.lock_touched(also=lots_of_made_lines([item]))
        order = found_or_raise(
            await self._orders.get_by_id(order_id),
            OrderNotFoundError,
            f"Order #{order_id} not found.",
        )
        item = await self._item_of(order_id, order_item_id)

        OrderRules.assert_can_remove_item(actor, order, item)
        assert_edit_version(item, expected_edit_version, what=f"Order item #{item.id}")
        if item.lot_position_id is not None and self._lots is not None:
            await assert_no_provisions(self._lots, item.lot_position_id)

        now = now_utc()

        # ── Deallocate ────────────────────────────────────────────────────
        affected_demand_ids = await deallocate_order_item(item, self._allocations)
        affected_source_item_demand_ids: set[int] = set()
        if self._source_item_allocations is not None:
            affected_source_item_demand_ids = await deallocate_source_item_order_item(
                item, self._source_item_allocations
            )

        # ── Delete the order item ─────────────────────────────────────────
        await self._order_items.delete(item)
        # The line's own changelog goes with it, so the order keeps the
        # record of what was removed. The entry carries its own time; the
        # order's fields did not change, so its last change stays.
        order.changes = append_changelog(
            order.changes,
            actor.full_name,
            f"Line {item.position} (order item #{item.id}, {item.quantity:g} {item.unit}) removed.",
        )
        await self._orders.save(order)
        self._reconciler.touch_orders([order_id])
        if item.lot_position_id is not None:
            # The deleted line no longer leads the reconciler to its position.
            self._reconciler.touch_positions([item.lot_position_id])
        # The deleted allocations no longer lead it to their demands either.
        self._reconciler.touch_demands(LifecycleAggregate.BOUGHT_DEMANDS, affected_demand_ids)
        self._reconciler.touch_demands(
            LifecycleAggregate.SOURCE_DEMANDS, affected_source_item_demand_ids
        )
        await self._reconciler.run(actor, now, reason=f"order item #{order_item_id} removed")

        await self._uow.commit()

        await recompute_schedule_after_commit(
            self._recompute,
            after=(
                f"removing order item #{order_item_id} "
                f"from order #{order_id}; the removal itself is committed."
            ),
        )

        log.info(
            f"Removed order item #{order_item_id} "
            f"from order #{order_id}. Deallocated {len(affected_demand_ids)} demand(s)."
        )

    async def _item_of(self, order_id: int, order_item_id: int) -> OrderItem:
        item = await self._order_items.get_by_id(order_item_id)
        if not item or item.order_id != order_id:
            raise OrderItemNotFoundError(
                f"Order item #{order_item_id} not found in order #{order_id}."
            )
        return item
