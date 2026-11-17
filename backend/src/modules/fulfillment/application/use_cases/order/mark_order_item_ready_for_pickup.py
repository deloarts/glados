"""
Records readiness for pickup from a supplier, optionally backdating the confirmation, and
recomputing downstream production order schedules if the item is linked to a lot position.
"""

from datetime import UTC
from datetime import datetime

from src.modules.fulfillment.application.dto.order_dto import OrderItemResult
from src.modules.fulfillment.application.mappers.order_mapper import OrderItemMapper
from src.modules.fulfillment.application.services.lifecycle_loader import AggregateIds
from src.modules.fulfillment.application.services.lifecycle_lock_plan import LockPlan
from src.modules.fulfillment.application.services.schedule_recompute_helpers import (
    recompute_downstream_position_machines,
)
from src.modules.fulfillment.application.use_cases.production_schedule.recompute_machine_schedule import (
    RecomputeMachineSchedule,
)
from src.modules.fulfillment.domain.errors import OrderItemNotFoundError
from src.modules.fulfillment.domain.errors import OrderNotFoundError
from src.modules.fulfillment.domain.services.order_rules import OrderRules
from src.modules.fulfillment.domain.value_objects.lifecycle_aggregate import LifecycleAggregate
from src.modules.fulfillment.ports.outbound.repositories.order_repository import (
    IOrderItemRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.order_repository import IOrderRepository
from src.modules.fulfillment.ports.outbound.repositories.production_lot_repository import (
    IProductionLotRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.production_order_repository import (
    IProductionOrderRepository,
)
from src.modules.platform.application.services.lookup import found_or_raise
from src.modules.platform.domain.entities.user import User
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork
from src.shared_kernel.domain.services.changelog_service import append_changelog
from src.shared_kernel.domain.services.clock import now_utc


class MarkOrderItemReadyForPickup:
    """Records that the supplier has confirmed a batch is ready to collect.

    Entirely optional and never required by any status transition, this
    only ever improves the scheduler's predecessor-readiness estimate for
    EXTERNAL/MIXED lot positions when set; skipping it changes nothing
    else about the order item's flow.
    """

    def __init__(
        self,
        order_item_repo: IOrderItemRepository,
        order_repo: IOrderRepository,
        lot_repo: IProductionLotRepository | None = None,
        production_order_repo: IProductionOrderRepository | None = None,
        recompute_schedule: RecomputeMachineSchedule | None = None,
        *,
        uow: IUnitOfWork,
        lock_plan: LockPlan | None = None,
    ) -> None:
        self._order_items = order_item_repo
        self._uow = uow
        self._lock_plan = lock_plan
        self._orders = order_repo
        self._lots = lot_repo
        self._production_orders = production_order_repo
        self._recompute = recompute_schedule

    async def execute(
        self,
        actor: User,
        order_id: int,
        order_item_id: int,
        pickup_at: datetime | None = None,
    ) -> OrderItemResult:
        # The order and the line are locked before they are read, so the
        # order's state checked below holds until the commit.
        if self._lock_plan is not None:
            await self._lock_plan.acquire(
                AggregateIds.of(
                    {
                        LifecycleAggregate.ORDERS: [order_id],
                        LifecycleAggregate.ORDER_ITEMS: [order_item_id],
                    }
                )
            )
        order = found_or_raise(
            await self._orders.get_by_id(order_id),
            OrderNotFoundError,
            f"Order #{order_id} not found.",
        )
        OrderRules.assert_can_write_orders(actor)

        order_item = await self._order_items.get_by_id(order_item_id)
        if not order_item or order_item.order_id != order_id:
            raise OrderItemNotFoundError(
                f"Order item #{order_item_id} not found in order #{order_id}."
            )
        OrderRules.assert_can_update_line(
            actor, order, order_item.status, f"Order item #{order_item.id}"
        )

        now = now_utc()
        # Callers may backdate the confirmation; a naive value is read as UTC
        # rather than silently mixing aware and naive timestamps in the column.
        if pickup_at is not None and pickup_at.tzinfo is None:
            pickup_at = pickup_at.replace(tzinfo=UTC)
        OrderRules.assert_ready_for_pickup(order, order_item, pickup_at or now, now)
        order_item.ready_for_pickup_date = pickup_at or now
        order_item.changed = now
        order_item.changes = append_changelog(
            order_item.changes, actor.full_name, "Marked as ready for pickup."
        )
        saved = await self._order_items.save(order_item)
        # Committed before the schedule recompute below, which only reads
        # committed rows.
        await self._uow.commit()
        log.info(f"Marked order item #{order_item_id} as ready for pickup.")

        if (
            saved.lot_position_id is not None
            and self._lots is not None
            and self._production_orders is not None
            and self._recompute is not None
        ):
            await recompute_downstream_position_machines(
                saved.lot_position_id, self._lots, self._production_orders, self._recompute
            )

        return OrderItemMapper.to_result(saved)
