"""
Splits one QUEUED production order into several, quantities must sum to
the original. Each part gets its own estimated_duration_minutes
(its own setup, since it's a separate machine run) and is appended to the
tail of the same queue: the order's machine, or its machine pool while no
machine is resolved, and the parts keep that pool.

The queue's lock, then the order's lot and then the order are locked
through the request's lock plan before the order is checked, and the new
parts are registered with the lifecycle reconciler as rows this transaction
created.
"""

from src.modules.fulfillment.application.dto.production_order_dto import ProductionOrderResult
from src.modules.fulfillment.application.dto.production_order_dto import SplitProductionOrderCommand
from src.modules.fulfillment.application.mappers.production_order_mapper import (
    ProductionOrderMapper,
)
from src.modules.fulfillment.application.services.lifecycle_reconciler import LifecycleReconciler
from src.modules.fulfillment.application.services.queue_scope_locks import assert_queue_scope_held
from src.modules.fulfillment.application.services.queue_scope_locks import lock_queue_scopes_first
from src.modules.fulfillment.application.use_cases.production_order._locks import lock_lot_and_order
from src.modules.fulfillment.application.use_cases.production_schedule.recompute_machine_schedule import (
    RecomputeMachineSchedule,
)
from src.modules.fulfillment.domain.entities.production_order import ProductionOrder
from src.modules.fulfillment.domain.errors import LotPositionNotFoundError
from src.modules.fulfillment.domain.errors import ProductionOrderNotFoundError
from src.modules.fulfillment.domain.errors import ProductionOrderNotSplittableError
from src.modules.fulfillment.domain.events.production_order_events import ProductionOrderCreated
from src.modules.fulfillment.domain.services.lot_event_service import build_lot_event
from src.modules.fulfillment.domain.services.production_order_rules import ProductionOrderRules
from src.modules.fulfillment.domain.services.production_order_rules import (
    assert_production_order_action,
)
from src.modules.fulfillment.domain.services.production_order_rules import (
    assert_split_sums_correctly,
)
from src.modules.fulfillment.domain.services.production_order_rules import (
    compute_estimated_duration_minutes,
)
from src.modules.fulfillment.domain.value_objects.lot_event_type import LotEventType
from src.modules.fulfillment.domain.value_objects.production_status import ProductionOrderStatus
from src.modules.fulfillment.ports.outbound.fulfillment_settings_repository import (
    IFulfillmentSettingsRepository,
)
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
from src.modules.platform.domain.services.edit_version import bump_edit_version
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.ports.outbound.event_bus_port import IEventBus
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork
from src.shared_kernel.domain.services.changelog_service import append_changelog
from src.shared_kernel.domain.services.clock import now_utc
from src.shared_kernel.domain.value_objects.lifecycle_action import LifecycleAction


class SplitProductionOrder:
    def __init__(
        self,
        order_repo: IProductionOrderRepository,
        lot_repo: IProductionLotRepository,
        settings_repo: IFulfillmentSettingsRepository,
        recompute_schedule: RecomputeMachineSchedule | None = None,
        *,
        event_bus: IEventBus,
        uow: IUnitOfWork,
        reconciler: LifecycleReconciler,
    ) -> None:
        self._orders = order_repo
        self._lots = lot_repo
        self._settings = settings_repo
        self._recompute = recompute_schedule
        self._bus = event_bus
        self._uow = uow
        self._reconciler = reconciler

    async def execute(
        self, actor: User, production_order_id: int, cmd: SplitProductionOrderCommand
    ) -> list[ProductionOrderResult]:
        ProductionOrderRules.assert_can_assign(actor)

        order = await self._orders.get_by_id(production_order_id)
        if not order:
            raise ProductionOrderNotFoundError(
                f"Production order #{production_order_id} not found."
            )
        self._assert_can_split(actor, order, cmd)

        position = found_or_raise(
            await self._lots.get_position_by_id(order.lot_position_id),
            LotPositionNotFoundError,
            f"Position #{order.lot_position_id} not found.",
        )
        # The parts draw places from the order's queue: its lock comes before
        # the row locks, from this unlocked read (queue_scope_locks.py).
        scopes = await lock_queue_scopes_first(
            self._orders,
            [(order.machine_id, order.machine_pool_id)] if len(cmd.quantities) > 1 else [],
        )
        _lot, order, position = await lock_lot_and_order(
            self._reconciler, self._lots, self._orders, position, order.id
        )
        self._assert_can_split(actor, order, cmd)
        steps = position.steps

        template = (await self._settings.get_production()).production_order_number_format
        now = now_utc()
        first_quantity, *rest_quantities = cmd.quantities

        # Serialized against a concurrent assign/reassign/reorder/auto-plan
        # drawing from the same queue by the scope lock taken above:
        # next_queue_sequence below is an unlocked read-then-increment (see
        # IProductionOrderRepository.lock_queue_scope). Each part order
        # still re-derives its own number from a fresh query (safe against
        # self-collision within this loop), the lock only guards against a
        # different transaction racing it. The scope is the order's machine,
        # or its pool while no machine is resolved.
        if rest_quantities:
            assert_queue_scope_held(scopes, order.machine_id, order.machine_pool_id, order.id)

        # A client that read the order before the split edits a stale copy,
        # so its version moves with the quantity and duration.
        bump_edit_version(order)
        order.quantity = first_quantity
        order.estimated_duration_minutes = compute_estimated_duration_minutes(steps, first_quantity)
        order.changed = now
        order.changes = append_changelog(
            order.changes, actor.full_name, f"Split: this part reduced to {first_quantity:.3f}."
        )
        saved_orders = [await self._orders.save(order)]

        new_orders = []
        for quantity in rest_quantities:
            new_order = ProductionOrder(
                id=0,
                created=now,
                changed=now,
                changes=append_changelog(
                    [], actor.full_name, f"Split from production order #{order.id}."
                ),
                production_order_number=await self._orders.next_production_order_number(template),
                status=ProductionOrderStatus.QUEUED,
                priority=order.priority,
                pinned=False,
                queue_sequence=await self._orders.next_queue_sequence(
                    order.machine_id, order.machine_pool_id
                ),
                quantity=quantity,
                quantity_completed=0.0,
                estimated_duration_minutes=compute_estimated_duration_minutes(steps, quantity),
                note=order.note,
                planned_start=None,
                planned_end=None,
                not_before=order.not_before,
                actual_start=None,
                actual_end=None,
                creator_id=actor.id,
                machine_id=order.machine_id,
                machine_pool_id=order.machine_pool_id,
                lot_position_id=order.lot_position_id,
            )
            saved_new = await self._orders.save(new_order)
            self._reconciler.touch_production_orders([saved_new.id], created=True)
            saved_orders.append(saved_new)
            new_orders.append(saved_new)

        await self._reconciler.run(actor, now)

        # One timeline entry per split, on the lot the position belongs to.
        await self._lots.record_event(
            build_lot_event(
                position.lot_id,
                actor,
                LotEventType.ORDER_SPLIT,
                "order",
                f"Production order #{order.id} split into {len(cmd.quantities)} part(s).",
                entity_id=order.id,
                payload={
                    "source_production_order_id": order.id,
                    "part_production_order_ids": [o.id for o in new_orders],
                    "quantities": list(cmd.quantities),
                },
            )
        )

        # Staged in the same transaction as the split (see event_outbox.py),
        # and ahead of the (fallible) schedule recompute below.
        for new_order in new_orders:
            await self._bus.publish(
                ProductionOrderCreated(
                    production_order_id=new_order.id,
                    machine_id=new_order.machine_id,
                    lot_position_id=new_order.lot_position_id,
                    creator_id=actor.id,
                    machine_pool_id=new_order.machine_pool_id,
                )
            )

        await self._uow.commit()

        await recompute_schedule_after_commit(
            self._recompute,
            after=(
                f"splitting production order "
                f"#{production_order_id}; the split itself is committed and its "
                f"events are published."
            ),
        )

        log.info(
            f"Split production order #{production_order_id} into {len(cmd.quantities)} part(s)."
        )
        return [ProductionOrderMapper.to_result(o) for o in saved_orders]

    @staticmethod
    def _assert_can_split(
        actor: User, order: ProductionOrder, cmd: SplitProductionOrderCommand
    ) -> None:
        assert_production_order_action(
            LifecycleAction.SPLIT, order, actor, refused=ProductionOrderNotSplittableError
        )
        # A pinned order changes only in the hands of a manager, as on every
        # other edit of it.
        ProductionOrderRules.assert_can_update(actor, order)
        assert_split_sums_correctly(cmd.quantities, order.quantity)
