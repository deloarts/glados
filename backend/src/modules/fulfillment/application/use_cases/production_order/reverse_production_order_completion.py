"""Reverses a mistaken completion of a production order.

A reversal is a completion row that books the original's pieces negative and
names it, the cancellation booking of a confirmation: both rows stay in the
record, every sum over the order's completions nets out, and the order's
completed count, which the reconciler derives from the rows, drops by the
accepted pieces. A completion is reversed
at most once, with a reason, and only while its pieces are still at the
position (assert_completion_reversible): one that rejected pieces, whose
disposition already changed the lot, and one whose pieces the next position
already used, completed, rejected or provided to the supplier of an external
next position, are refused. manage:production_orders is checked before anything
is read. The production order intent table decides the order statuses and
that the lot is neither on hold, since a held lot is resumed before its
record changes, nor finished; a finished lot keeps its record as it ended.

The lot and then the order are locked before anything is read, as for a
completion, so a reversal and a completion on one lot serialize. The
lifecycle reconciler derives the order, its position and the lot again; an
order that leaves COMPLETED takes the next free place of its queue.
"""

from src.modules.fulfillment.application.dto.production_order_dto import ProductionOrderResult
from src.modules.fulfillment.application.mappers.production_order_mapper import (
    ProductionOrderMapper,
)
from src.modules.fulfillment.application.services.lifecycle_reconciler import LifecycleReconciler
from src.modules.fulfillment.application.use_cases.production_order._locks import lock_lot_and_order
from src.modules.fulfillment.application.use_cases.production_schedule.recompute_machine_schedule import (
    RecomputeMachineSchedule,
)
from src.modules.fulfillment.domain.entities.lot_position import LotPosition
from src.modules.fulfillment.domain.entities.production_lot import ProductionLot
from src.modules.fulfillment.domain.entities.production_order_completion import (
    ProductionOrderCompletion,
)
from src.modules.fulfillment.domain.errors import CompletionNotFoundError
from src.modules.fulfillment.domain.errors import CompletionNotReversibleError
from src.modules.fulfillment.domain.errors import LotPositionNotFoundError
from src.modules.fulfillment.domain.errors import ProductionOrderNotFoundError
from src.modules.fulfillment.domain.events.production_order_events import (
    ProductionOrderCompletionReversed,
)
from src.modules.fulfillment.domain.services.lot_event_service import build_lot_event
from src.modules.fulfillment.domain.services.production_order_rules import (
    assert_completion_reversible,
)
from src.modules.fulfillment.domain.services.production_order_rules import (
    assert_production_order_action,
)
from src.modules.fulfillment.domain.services.production_order_rules import production_order_context
from src.modules.fulfillment.domain.value_objects.lot_event_type import LotEventType
from src.modules.fulfillment.domain.value_objects.lot_status import TERMINAL_LOT_STATUSES
from src.modules.fulfillment.domain.value_objects.lot_status import LotStatus
from src.modules.fulfillment.ports.outbound.fulfillment_settings_repository import (
    IFulfillmentSettingsRepository,
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
from src.modules.platform.application.services.lookup import found_or_raise
from src.modules.platform.application.services.schedule_recompute_port import (
    recompute_schedule_after_commit,
)
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.services.crud_permission_rules import assert_has_permission
from src.modules.platform.domain.services.datetime_filters import resolve_actor_timezone
from src.modules.platform.domain.value_objects.permission import Permission
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.ports.outbound.event_bus_port import IEventBus
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork
from src.shared_kernel.domain.services.changelog_service import append_changelog
from src.shared_kernel.domain.services.clock import now_utc
from src.shared_kernel.domain.value_objects.lifecycle_action import LifecycleAction


class ReverseProductionOrderCompletion:
    def __init__(
        self,
        order_repo: IProductionOrderRepository,
        lot_repo: IProductionLotRepository,
        order_item_repo: IOrderItemRepository,
        settings_repo: IFulfillmentSettingsRepository,
        *,
        uow: IUnitOfWork,
        event_bus: IEventBus,
        reconciler: LifecycleReconciler,
        recompute_schedule: RecomputeMachineSchedule | None = None,
    ) -> None:
        self._orders = order_repo
        self._lots = lot_repo
        self._order_items = order_item_repo
        self._settings = settings_repo
        self._uow = uow
        self._bus = event_bus
        self._reconciler = reconciler
        self._recompute = recompute_schedule

    async def execute(
        self, actor: User, production_order_id: int, completion_id: int, reason: str
    ) -> ProductionOrderResult:
        assert_has_permission(
            actor, Permission.MANAGE_PRODUCTION_ORDERS, "reverse", "production order completions"
        )
        order = found_or_raise(
            await self._orders.get_by_id(production_order_id),
            ProductionOrderNotFoundError,
            f"Production order #{production_order_id} not found.",
        )
        position = found_or_raise(
            await self._lots.get_position_by_id(order.lot_position_id),
            LotPositionNotFoundError,
            f"Position #{order.lot_position_id} not found.",
        )
        lot, order, position = await lock_lot_and_order(
            self._reconciler, self._lots, self._orders, position, production_order_id
        )
        # A held lot keeps its pieces where they are until it is resumed, and
        # a finished lot keeps its record as it ended.
        assert_production_order_action(
            LifecycleAction.REVERSE_COMPLETION,
            order,
            actor,
            production_order_context(
                order,
                lot_held=lot.status == LotStatus.ON_HOLD,
                lot_terminal=lot.status in TERMINAL_LOT_STATUSES,
            ),
            refused=CompletionNotReversibleError,
        )

        completions = await self._orders.get_completions(order.id)
        completion = next((c for c in completions if c.id == completion_id), None)
        if completion is None:
            raise CompletionNotFoundError(
                f"Completion #{completion_id} not found on production order #{order.id}."
            )
        assert_completion_reversible(
            completion,
            reversed_already=any(c.reverses_completion_id == completion.id for c in completions),
            completed_after=position.quantity_completed - completion.quantity_accepted,
            used_downstream=await self._used_downstream(lot, position),
        )

        now = now_utc()
        zone = resolve_actor_timezone((await self._settings.get_general()).default_timezone)
        reversal = await self._orders.save_completion(
            ProductionOrderCompletion(
                id=0,
                production_order_id=order.id,
                quantity=-completion.quantity,
                quantity_accepted=-completion.quantity_accepted,
                quantity_rejected=0.0,
                completion_date=now.astimezone(zone).date(),
                note=reason,
                operator_id=actor.id,
                recorded_by_id=actor.id,
                created=now,
                reverses_completion_id=completion.id,
                machine_id=completion.machine_id,
            )
        )
        order.changed = now
        order.changes = append_changelog(
            order.changes,
            actor.full_name,
            f"Completion #{completion.id} of {completion.quantity:.3f} reversed: {reason}",
        )
        await self._orders.save(order)
        await self._lots.record_event(
            build_lot_event(
                lot.id,
                actor,
                LotEventType.ORDER_COMPLETION_REVERSED,
                "order",
                f"Completion #{completion.id} of {completion.quantity:.3f} on production order "
                f"{order.production_order_number} reversed: {reason}",
                entity_id=order.id,
                payload={
                    "completion_id": completion.id,
                    "reversal_id": reversal.id,
                    "quantity": completion.quantity,
                    "reason": reason,
                },
            )
        )

        await self._reconciler.run(actor, now, reason=f"completion #{completion.id} reversed")
        await self._bus.publish(
            ProductionOrderCompletionReversed(
                production_order_id=order.id,
                completion_id=completion.id,
                reversal_id=reversal.id,
                actor_id=actor.id,
            )
        )
        await self._uow.commit()

        await recompute_schedule_after_commit(
            self._recompute,
            after=(
                f"reversing completion #{completion.id} of production order #{order.id}; "
                "the reversal itself is committed."
            ),
        )
        log.info(f"Reversed completion #{completion.id} of production order #{order.id}.")
        reversed_order = found_or_raise(
            await self._orders.get_by_id(order.id),
            ProductionOrderNotFoundError,
            f"Production order #{order.id} not found.",
        )
        return ProductionOrderMapper.to_result(reversed_order)

    async def _used_downstream(self, lot: ProductionLot, position: LotPosition) -> float:
        """What the next position of the lot already used of this one's
        pieces: what it completed, and what its orders and its live line
        rejected, which used input just as well, or what was provided to the
        supplier of an external next position, when that is more, since a
        provided piece has left the plant and its delivery comes back as a
        completed one. 0 for the last position."""
        successor = next((p for p in lot.positions if p.sequence == position.sequence + 1), None)
        if successor is None:
            return 0.0
        rejected = 0.0
        for order in await self._orders.get_by_lot_position_id(successor.id):
            rejected += sum(
                c.quantity_rejected for c in await self._orders.get_completions(order.id)
            )
        for line in await self._order_items.get_by_lot_position_ids([successor.id]):
            if line.canceled_at is None:
                rejected += line.quantity_rejected
        provided = sum((p.quantity for p in await self._lots.get_provisions(successor.id)), 0.0)
        return max(successor.quantity_completed + rejected, provided)
