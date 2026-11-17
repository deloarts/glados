"""
Merges several QUEUED production orders (same machine, same machine pool,
same lot position) back into one, the inverse of split. Keeps the first
order (lowest queue_sequence), sums quantities onto it, deletes* the rest.

Duration is recomputed from the position's steps for the merged quantity
(compute_estimated_duration_minutes), not summed from the parts' own
durations, each part's estimated_duration_minutes already includes a
full setup pass, since each order pays its own setup as a separate
machine run, so summing would double- or triple-count setup once the
parts become one run again.

*"delete" here means cancel + zero out rather than a hard row delete,
ProductionOrderCompletion rows only exist for started orders and QUEUED
orders never have any, so there's nothing to lose; canceling keeps the
audit trail (an order that existed briefly and was merged away) instead
of erasing it. A merged-away order gets canceled_at, and the lifecycle
reconciler derives its CANCELED status and publishes its
ProductionOrderCanceled. The lot and then the orders are locked through
the request's lock plan before they are checked, the edit version the
client read of each order among the checks, and since a merge cannot be
taken back, every order it changes moves on to its next edit version.
"""

from src.modules.fulfillment.application.dto.production_order_dto import (
    MergeProductionOrdersCommand,
)
from src.modules.fulfillment.application.dto.production_order_dto import ProductionOrderResult
from src.modules.fulfillment.application.mappers.production_order_mapper import (
    ProductionOrderMapper,
)
from src.modules.fulfillment.application.services.lifecycle_loader import AggregateIds
from src.modules.fulfillment.application.services.lifecycle_reconciler import LifecycleReconciler
from src.modules.fulfillment.application.use_cases.production_schedule.recompute_machine_schedule import (
    RecomputeMachineSchedule,
)
from src.modules.fulfillment.domain.entities.production_order import ProductionOrder
from src.modules.fulfillment.domain.errors import LotPositionNotFoundError
from src.modules.fulfillment.domain.errors import ProductionOrderCannotMergeError
from src.modules.fulfillment.domain.errors import ProductionOrderNotFoundError
from src.modules.fulfillment.domain.services.lot_event_service import build_lot_event
from src.modules.fulfillment.domain.services.production_order_rules import ProductionOrderRules
from src.modules.fulfillment.domain.services.production_order_rules import assert_can_merge
from src.modules.fulfillment.domain.services.production_order_rules import (
    assert_production_order_action,
)
from src.modules.fulfillment.domain.services.production_order_rules import (
    compute_estimated_duration_minutes,
)
from src.modules.fulfillment.domain.value_objects.lifecycle_aggregate import LifecycleAggregate
from src.modules.fulfillment.domain.value_objects.lot_event_type import LotEventType
from src.modules.fulfillment.ports.outbound.repositories.production_lot_repository import (
    IProductionLotRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.production_order_repository import (
    IProductionOrderRepository,
)
from src.modules.platform.application.services.lookup import found_or_raise
from src.modules.platform.application.services.schedule_recompute_port import (
    recompute_schedule_after_commit,
)
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.services.edit_version import assert_edit_version
from src.modules.platform.domain.services.edit_version import bump_edit_version
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.ports.outbound.event_bus_port import IEventBus
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork
from src.shared_kernel.domain.services.changelog_service import append_changelog
from src.shared_kernel.domain.services.clock import now_utc
from src.shared_kernel.domain.value_objects.lifecycle_action import LifecycleAction


class MergeProductionOrders:
    def __init__(
        self,
        order_repo: IProductionOrderRepository,
        lot_repo: IProductionLotRepository,
        recompute_schedule: RecomputeMachineSchedule | None = None,
        *,
        event_bus: IEventBus,
        uow: IUnitOfWork,
        reconciler: LifecycleReconciler,
    ) -> None:
        self._orders = order_repo
        self._lots = lot_repo
        self._recompute = recompute_schedule
        self._bus = event_bus
        self._uow = uow
        self._reconciler = reconciler

    async def execute(
        self, actor: User, cmd: MergeProductionOrdersCommand
    ) -> ProductionOrderResult:
        ProductionOrderRules.assert_can_assign(actor)

        orders = await self._load(cmd.production_order_ids, refresh=False)
        self._assert_can_merge(actor, orders)
        position = found_or_raise(
            await self._lots.get_position_by_id(orders[0].lot_position_id),
            LotPositionNotFoundError,
            f"Position #{orders[0].lot_position_id} not found.",
        )

        self._reconciler.touch_production_orders([o.id for o in orders])
        await self._reconciler.lock_touched(
            also=AggregateIds.of({LifecycleAggregate.LOTS: [position.lot_id]})
        )
        orders = await self._load(cmd.production_order_ids, refresh=True)
        self._assert_can_merge(actor, orders)
        for order in orders:
            assert_edit_version(
                order,
                cmd.expected_edit_versions.get(order.id),
                what=f"Production order #{order.id}",
            )
        # The steps the merged duration is computed from, read again with
        # the lot under its lock, so a structure edit committed meanwhile is
        # seen.
        lot = await self._lots.get_by_id_for_update(position.lot_id)
        locked = next((p for p in lot.positions if p.id == position.id), None) if lot else None
        if locked is None:
            raise LotPositionNotFoundError(f"Position #{position.id} not found.")
        position = locked

        orders.sort(key=lambda o: o.queue_sequence)
        keeper, *rest = orders
        now = now_utc()

        # A merge cannot be taken back, so every order it changes moves on.
        bump_edit_version(keeper)
        keeper.quantity = sum(o.quantity for o in orders)
        keeper.estimated_duration_minutes = compute_estimated_duration_minutes(
            position.steps, keeper.quantity
        )
        keeper.changed = now
        merged_ids = ", ".join(f"#{o.id}" for o in rest)
        keeper.changes = append_changelog(
            keeper.changes, actor.full_name, f"Merged with production order(s) {merged_ids}."
        )
        saved_keeper = await self._orders.save(keeper)

        for order in rest:
            order.quantity = 0.0
            bump_edit_version(order)
            order.canceled_at = now
            order.changed = now
            order.changes = append_changelog(
                order.changes, actor.full_name, f"Merged into production order #{keeper.id}."
            )
            await self._orders.save(order)

        await self._reconciler.run(actor, now)

        # One timeline entry per merge, on the lot the position belongs to.
        await self._lots.record_event(
            build_lot_event(
                position.lot_id,
                actor,
                LotEventType.ORDER_MERGED,
                "order",
                f"Production order(s) {merged_ids} merged into #{keeper.id} "
                f"(quantity {keeper.quantity:.3f}).",
                entity_id=keeper.id,
                payload={
                    "keeper_production_order_id": keeper.id,
                    "merged_production_order_ids": [o.id for o in rest],
                    "quantity": keeper.quantity,
                },
            )
        )

        await self._uow.commit()

        await recompute_schedule_after_commit(
            self._recompute,
            after=(
                f"merging production order(s) {merged_ids} into #{keeper.id}; the merge "
                f"itself is committed."
            ),
        )

        log.info(f"Merged production order(s) {merged_ids} into #{keeper.id}.")
        return ProductionOrderMapper.to_result(saved_keeper)

    async def _load(self, ids: list[int], *, refresh: bool) -> list[ProductionOrder]:
        orders = await self._orders.get_by_ids(ids, refresh=refresh)
        if len(orders) != len(set(ids)):
            missing = set(ids) - {o.id for o in orders}
            raise ProductionOrderNotFoundError(f"Production order(s) {missing} not found.")
        return orders

    @staticmethod
    def _assert_can_merge(actor: User, orders: list[ProductionOrder]) -> None:
        assert_can_merge(orders)
        for order in orders:
            assert_production_order_action(
                LifecycleAction.MERGE, order, actor, refused=ProductionOrderCannotMergeError
            )
            # A pinned order changes only in the hands of a manager, as on
            # every other edit of it.
            ProductionOrderRules.assert_can_update(actor, order)
