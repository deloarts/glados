"""
Cancels a single order line on which nothing was delivered or lost yet. The
line keeps its row as the record of what was ordered: its canceled_at is
recorded, every allocation of both families on it is released whatever its
demand's status, and the lifecycle reconciler derives the statuses of the
line, its order and the demands that lost one, a fulfilled or canceled
demand keeping its status by its intent. A line that received pieces is closed short
instead (close_order_item_short.py), and a pending or requested line can also
be removed outright (delete_order_item.py).

A MADE line is canceled with its own facts only, as the order and lot cancel
cascades cancel one; the position it supplies follows from the derivation
that reads the position's live lines. Its lot is locked first, as the one
lock order has it.
"""

from src.modules.fulfillment.application.dto.order_dto import OrderItemResult
from src.modules.fulfillment.application.mappers.order_mapper import OrderItemMapper
from src.modules.fulfillment.application.services.lifecycle_reconciler import LifecycleReconciler
from src.modules.fulfillment.application.use_cases.order._lines import lots_of_made_lines
from src.modules.fulfillment.application.use_cases.order._lines import read_order_line
from src.modules.fulfillment.application.use_cases.order._lines import release_line_allocations
from src.modules.fulfillment.application.use_cases.production_schedule.recompute_machine_schedule import (
    RecomputeMachineSchedule,
)
from src.modules.fulfillment.domain.services.order_rules import OrderRules
from src.modules.fulfillment.domain.value_objects.lifecycle_aggregate import LifecycleAggregate
from src.modules.fulfillment.ports.outbound.repositories.bought_item_demand_repository import (
    IBoughtItemAllocationRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.order_repository import (
    IOrderItemRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.order_repository import IOrderRepository
from src.modules.fulfillment.ports.outbound.repositories.source_item_demand_repository import (
    ISourceItemAllocationRepository,
)
from src.modules.platform.application.services.schedule_recompute_port import (
    recompute_schedule_after_commit,
)
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.services.edit_version import assert_edit_version
from src.modules.platform.domain.services.edit_version import bump_edit_version
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork
from src.shared_kernel.domain.services.changelog_service import append_changelog
from src.shared_kernel.domain.services.clock import now_utc


class CancelOrderItem:
    """Cancels one line of an order; see the module docstring. Needs the
    order's update permission, as removing a line does."""

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
    ) -> None:
        self._orders = order_repo
        self._order_items = order_item_repo
        self._allocations = allocation_repo
        self._recompute = recompute_schedule
        self._uow = uow
        self._reconciler = reconciler
        self._source_item_allocations = source_item_allocation_repo

    async def execute(
        self,
        actor: User,
        order_id: int,
        order_item_id: int,
        *,
        expected_edit_version: int | None = None,
    ) -> OrderItemResult:
        _, item = await read_order_line(self._orders, self._order_items, order_id, order_item_id)

        self._reconciler.touch_order_items([order_item_id])
        await self._reconciler.lock_touched(also=lots_of_made_lines([item]))
        order, item = await read_order_line(
            self._orders, self._order_items, order_id, order_item_id
        )

        OrderRules.assert_can_cancel_line(actor, order, item)
        assert_edit_version(item, expected_edit_version, what=f"Order item #{item.id}")

        now = now_utc()
        bump_edit_version(item)
        item.canceled_at = now
        item.changed = now
        item.changes = append_changelog(item.changes, actor.full_name, "Canceled.")
        await self._order_items.save(item)
        bought_ids, source_ids = await release_line_allocations(
            item, self._allocations, self._source_item_allocations
        )

        self._reconciler.touch_demands(LifecycleAggregate.BOUGHT_DEMANDS, bought_ids)
        self._reconciler.touch_demands(LifecycleAggregate.SOURCE_DEMANDS, source_ids)
        await self._reconciler.run(actor, now, reason=f"order item #{order_item_id} canceled")

        await self._uow.commit()

        await recompute_schedule_after_commit(
            self._recompute,
            after=(f"canceling order item #{order_item_id}; the cancellation itself is committed."),
        )

        log.info(
            f"Canceled order item #{order_item_id} of order #{order_id}. "
            f"Deallocated {len(bought_ids) + len(source_ids)} demand(s)."
        )
        canceled = await self._order_items.get_by_id(order_item_id)
        return OrderItemMapper.to_result(canceled or item)
