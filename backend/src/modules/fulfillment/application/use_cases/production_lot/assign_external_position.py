"""
Assigning an EXTERNAL position to an order IS the supplier assignment,
no separate "assign supplier" step. Creates an OrderItem with
line_type=MADE, bought_item_id=None, lot_position_id=position_id.

The line carries no name of its own: its display identity is resolved
live from lot_position -> lot -> made_item every time it is read, so
renaming the made item updates order lines already on an order. Only
VIRTUAL lines, the one line type with no catalogue row behind it,
store a name in virtual_name.

Both use cases lock the lot, then the order line and its order, through the
request's lock plan, and the lifecycle reconciler derives the kind and status
of the position, the status of the lot and that of the order with the line
added or removed. An order someone canceled takes no new line; one that is
canceled only because every line is canceled still does. A position holds at
most one open line; a canceled line stays beside a new one as history, and a
line closed short stays beside the line that takes the rest. The
line belongs to the lot's project, whatever project the client names, and an
assignment is new work for that project, so it must be active.
"""

from datetime import datetime

from src.modules.catalogue.domain.errors import MadeItemNotFoundError
from src.modules.catalogue.ports.outbound.catalogue_queries import IMadeItemQueries
from src.modules.fulfillment.application.dto.production_lot_dto import AssignExternalPositionCommand
from src.modules.fulfillment.application.dto.production_lot_dto import LotPositionResult
from src.modules.fulfillment.application.mappers.production_lot_mapper import LotPositionMapper
from src.modules.fulfillment.application.services.lifecycle_loader import AggregateIds
from src.modules.fulfillment.application.services.lifecycle_reconciler import LifecycleReconciler
from src.modules.fulfillment.application.services.lot_provisions import assert_no_provisions
from src.modules.fulfillment.domain.entities.lot_position import EarlierOrderLine
from src.modules.fulfillment.domain.entities.lot_position import LotPosition
from src.modules.fulfillment.domain.entities.order_item import OrderItem
from src.modules.fulfillment.domain.errors import LotInvalidStatusTransitionError
from src.modules.fulfillment.domain.errors import LotPositionAlreadyAssignedError
from src.modules.fulfillment.domain.errors import LotPositionNotAssignableError
from src.modules.fulfillment.domain.errors import LotPositionNotFoundError
from src.modules.fulfillment.domain.errors import LotPositionQuantityExceedsRemainingError
from src.modules.fulfillment.domain.errors import OrderItemNotFoundError
from src.modules.fulfillment.domain.errors import OrderNotFoundError
from src.modules.fulfillment.domain.events.lot_events import LotPositionAssigned
from src.modules.fulfillment.domain.services.lot_event_service import build_lot_event
from src.modules.fulfillment.domain.services.lot_rules import LotRules
from src.modules.fulfillment.domain.services.lot_rules import PositionRefusal
from src.modules.fulfillment.domain.services.lot_rules import lot_position_context
from src.modules.fulfillment.domain.services.lot_rules import lot_position_refusal
from src.modules.fulfillment.domain.services.order_rules import OrderRules
from src.modules.fulfillment.domain.value_objects.lifecycle_aggregate import LifecycleAggregate
from src.modules.fulfillment.domain.value_objects.lot_event_type import LotEventType
from src.modules.fulfillment.domain.value_objects.lot_status import LotStatus
from src.modules.fulfillment.domain.value_objects.order_status import OrderItemStatus
from src.modules.fulfillment.domain.value_objects.order_status import OrderLineType
from src.modules.fulfillment.ports.outbound.repositories.order_repository import (
    IOrderItemRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.order_repository import IOrderRepository
from src.modules.fulfillment.ports.outbound.repositories.production_lot_repository import (
    IProductionLotRepository,
)
from src.modules.platform.application.services.lookup import found_or_raise
from src.modules.platform.application.services.schedule_recompute_port import ScheduleRecompute
from src.modules.platform.application.services.schedule_recompute_port import (
    recompute_schedule_after_commit,
)
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.services.quantities import quantity_gt
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.ports.outbound.event_bus_port import IEventBus
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork
from src.modules.workspace.domain.errors import ProjectNotFoundError
from src.modules.workspace.domain.policies.project_activity import assert_project_active
from src.modules.workspace.ports.outbound.workspace_queries import IProjectQueries
from src.shared_kernel.domain.services.changelog_service import append_changelog
from src.shared_kernel.domain.services.clock import now_utc
from src.shared_kernel.domain.value_objects.lifecycle_action import LifecycleAction


def _the_lot(lot_id: int) -> AggregateIds:
    """A lot for the lock plan, taken before the orders and lines."""
    return AggregateIds.of({LifecycleAggregate.LOTS: [lot_id]})


class AssignExternalPosition:
    def __init__(
        self,
        lot_repo: IProductionLotRepository,
        made_item_repo: IMadeItemQueries,
        order_repo: IOrderRepository,
        order_item_repo: IOrderItemRepository,
        *,
        project_repo: IProjectQueries,
        event_bus: IEventBus,
        uow: IUnitOfWork,
        reconciler: LifecycleReconciler,
        recompute_schedule: ScheduleRecompute | None = None,
    ) -> None:
        self._lots = lot_repo
        self._made_items = made_item_repo
        self._orders = order_repo
        self._order_items = order_item_repo
        self._projects = project_repo
        self._bus = event_bus
        self._uow = uow
        self._reconciler = reconciler
        self._recompute = recompute_schedule

    async def execute(
        self, actor: User, lot_id: int, position_id: int, cmd: AssignExternalPositionCommand
    ) -> LotPositionResult:
        # Checked before the lot lock, so a position that cannot be assigned
        # fails early.
        self._assert_assignable(
            actor, await self._lots.get_position_by_id(position_id), lot_id, position_id
        )
        # A lot never changes its project, so the unlocked read names the
        # project to lock: shared, before the lifecycle locks, as every
        # writer of new work for a project takes it
        # (IProjectQueries.lock_for_share).
        project_id = found_or_raise(
            await self._lots.get_by_id(lot_id),
            LotPositionNotFoundError,
            f"Lot #{lot_id} not found.",
        ).project_id
        await self._projects.lock_for_share([project_id])
        assert_project_active(
            found_or_raise(
                await self._projects.get_by_id(project_id),
                ProjectNotFoundError,
                f"Project #{project_id} not found.",
            ),
            work="external assignments",
        )

        # The lot and the order, in one acquisition in the lock order. The
        # locked read is hoisted above the remaining-quantity check: a
        # force-canceled/completed lot must not grow live order items, and
        # the position checks and `remaining` run again on the locked lot's
        # own position object, which is also the one written below, so an
        # assignment or a production order committed meanwhile counts (see
        # IProductionLotRepository.get_by_id_for_update).
        self._reconciler.touch_orders([cmd.order_id])
        await self._reconciler.lock_touched(also=_the_lot(lot_id))
        now = now_utc()
        saved_order_item, saved_position = await self.assign_under_lock(
            actor, lot_id, position_id, cmd, now
        )
        await self._reconciler.run(actor, now)
        # Staged in the same transaction as the assignment
        # (see event_outbox.py): publish before commit, always.
        await self._bus.publish(
            LotPositionAssigned(
                lot_id=lot_id,
                position_id=position_id,
                order_id=cmd.order_id,
                order_item_id=saved_order_item.id,
                actor_id=actor.id,
            )
        )

        await self._uow.commit()

        # The supplier line's dates now feed the positions after this one.
        await recompute_schedule_after_commit(
            self._recompute,
            after=f"assigning position #{position_id} of lot #{lot_id}; the line is committed.",
        )
        log.info(
            f"Assigned position #{position_id} of lot #{lot_id} "
            f"to order #{cmd.order_id} (item #{saved_order_item.id})."
        )
        result_position = found_or_raise(
            await self._lots.get_position_by_id(saved_position.id),
            LotPositionNotFoundError,
            f"Position #{saved_position.id} not found after save.",
        )
        return LotPositionMapper.to_result(result_position)

    async def assign_under_lock(
        self,
        actor: User,
        lot_id: int,
        position_id: int,
        cmd: AssignExternalPositionCommand,
        now: datetime,
        *,
        quote_request_line_id: int | None = None,
    ) -> tuple[OrderItem, LotPosition]:
        """Adds the MADE line for the position once the caller locked the lot
        and the order and checked the lot's project active, without running
        the reconciler, publishing the assignment or committing; returns the
        line and the position."""
        lot = found_or_raise(
            await self._lots.get_by_id_for_update(lot_id),
            LotPositionNotFoundError,
            f"Lot #{lot_id} not found.",
        )
        position = self._assert_assignable(
            actor,
            next((p for p in lot.positions if p.id == position_id), None),
            lot_id,
            position_id,
        )
        # A position takes one open line, which a partial unique index on
        # order_item.lot_position_id enforces; its canceled lines and its
        # lines closed short stay beside the new one. The line read here is
        # the newest live one under the lock.
        linked = await self._order_items.get_by_lot_position_id(position_id)
        live = linked if linked is not None and linked.canceled_at is None else None
        context = lot_position_context(position, lot.status, live)
        refusal = lot_position_refusal(LifecycleAction.ASSIGN_EXTERNAL, position, context, actor)
        if refusal is PositionRefusal.LIVE_LINE and live is not None:
            raise LotPositionAlreadyAssignedError(
                f"Position #{position_id} is still linked to order item #{live.id} "
                f"({live.status.value}) and cannot take another order item."
            )
        if refusal is PositionRefusal.LOT_TERMINAL:
            raise LotInvalidStatusTransitionError(
                f"Lot #{lot_id} is {lot.status.value} and cannot be assigned new order items."
            )
        self._raise_for(refusal, position)

        remaining = context.remaining
        quantity = cmd.quantity if cmd.quantity is not None else remaining
        if not quantity_gt(quantity, 0.0) or quantity_gt(quantity, remaining):
            raise LotPositionQuantityExceedsRemainingError(
                f"Position #{position_id} has {remaining:.3f} remaining; cannot assign "
                f"{quantity:.3f} externally."
            )

        order = found_or_raise(
            await self._orders.get_by_id(cmd.order_id),
            OrderNotFoundError,
            f"Order #{cmd.order_id} not found.",
        )
        OrderRules.assert_can_update_line(actor, order, OrderItemStatus.PENDING, "A new line")
        OrderRules.assert_can_add_line(order)

        found_or_raise(
            await self._made_items.get_by_id(lot.made_item_id),
            MadeItemNotFoundError,
            f"Catalogue item #{lot.made_item_id} not found.",
        )

        order_item = OrderItem(
            id=0,
            created=now,
            changed=now,
            changes=append_changelog(
                [], actor.full_name, f"Order item created for lot {lot.lot_number!r}."
            ),
            status=OrderItemStatus.default(),
            position=await self._order_items.next_position(cmd.order_id),
            quantity=quantity,
            quantity_delivered=0.0,
            unit=cmd.unit,
            items_per_unit=cmd.items_per_unit,
            price=cmd.price,
            note=None,
            ordered_date=None,
            expected_delivery_date=cmd.expected_delivery_date,
            delivery_date=None,
            storage_place=None,
            expected_pickup_date=cmd.expected_pickup_date,
            ready_for_pickup_date=None,
            creator_id=actor.id,
            orderer_id=None,
            receiver_id=None,
            bought_item_id=None,
            order_id=cmd.order_id,
            supplier_id=order.supplier_id,
            project_id=lot.project_id,
            line_type=OrderLineType.MADE,
            lot_position_id=position.id,
            source_item_id=None,
            virtual_name=None,
            quote_request_line_id=quote_request_line_id,
        )
        OrderRules.assert_valid_line_type(order_item)
        saved_order_item = await self._order_items.save(order_item)
        self._reconciler.touch_order_items([saved_order_item.id], created=True)

        # Keep the in-memory position's denormalized OrderItem fields
        # consistent immediately, rather than relying solely on a later
        # repository re-fetch to re-derive them (mirrors what
        # _enrich_positions_with_order_info would populate).
        if live is not None:
            position.closed_lines_quantity += live.quantity
            position.closed_lines_delivered += live.quantity_delivered
            # The position's order fields were read from this same line.
            same_line = position.order_item_id == live.id
            position.earlier_order_lines.insert(
                0,
                EarlierOrderLine(
                    order_item_id=live.id,
                    order_id=live.order_id,
                    order_number=position.order_number if same_line else "",
                    supplier_name=live.supplier_name,
                    quantity=live.quantity,
                    quantity_delivered=live.quantity_delivered,
                    unit=live.unit,
                    closed_short=live.closed_short_at is not None,
                ),
            )
        position.order_item_id = saved_order_item.id
        position.order_item_closed_short = False
        position.order_id = saved_order_item.order_id
        position.order_number = order.order_number
        position.supplier_name = saved_order_item.supplier_name or ""
        position.order_item_status = saved_order_item.status
        position.expected_delivery_date = saved_order_item.expected_delivery_date
        position.order_item_quantity = saved_order_item.quantity
        position.order_item_quantity_delivered = saved_order_item.quantity_delivered

        position.changed = now
        position.changes = append_changelog(
            position.changes,
            actor.full_name,
            f"Assigned to order #{cmd.order_id} (item #{saved_order_item.id}).",
        )
        saved_position = await self._lots.save_position(position)
        self._reconciler.touch_positions([saved_position.id])

        await self._lots.record_event(
            build_lot_event(
                lot_id,
                actor,
                LotEventType.POSITION_ASSIGNED_EXTERNAL,
                "position",
                f"Position #{position_id} assigned to order #{cmd.order_id} "
                f"(item #{saved_order_item.id}).",
                entity_id=position_id,
                payload={"order_id": cmd.order_id, "order_item_id": saved_order_item.id},
            )
        )
        return saved_order_item, saved_position

    @staticmethod
    def _assert_assignable(
        actor: User, position: LotPosition | None, lot_id: int, position_id: int
    ) -> LotPosition:
        """The position exists on the lot, has no live order line yet or only
        lines closed short, and is UNASSIGNED or INTERNAL unless its line was
        closed short, by the assign external rule of the lot position intent
        table. The lot's own state is checked under its
        lock."""
        if not position or position.lot_id != lot_id:
            raise LotPositionNotFoundError(f"Position #{position_id} not found on lot #{lot_id}.")
        if position.order_item_id is not None and not position.order_item_closed_short:
            raise LotPositionAlreadyAssignedError(
                f"Position #{position_id} is already assigned to an order."
            )
        refusal = lot_position_refusal(
            LifecycleAction.ASSIGN_EXTERNAL,
            position,
            lot_position_context(position, LotStatus.DRAFT),
            actor,
        )
        if refusal in (PositionRefusal.KIND, PositionRefusal.LIVE_LINE):
            AssignExternalPosition._raise_for(refusal, position)
        return position

    @staticmethod
    def _raise_for(refusal: PositionRefusal | None, position: LotPosition) -> None:
        """Raises the error assign external has always answered a refused
        position with; the lot's state and the remaining quantity are
        reported by the caller, which knows the lot and the request."""
        if refusal is PositionRefusal.LIVE_LINE:
            raise LotPositionAlreadyAssignedError(
                f"Position #{position.id} is already assigned to an order."
            )
        if refusal is PositionRefusal.KIND:
            raise LotPositionNotAssignableError(
                f"Position #{position.id} has kind {position.kind.value!r} and cannot be "
                f"assigned to an order."
            )


class UnassignExternalPosition:
    """Only while the linked order item hasn't progressed past
    PENDING/REQUESTED, once ORDERED, unassigning would silently orphan a
    real purchase, so it's blocked."""

    def __init__(
        self,
        lot_repo: IProductionLotRepository,
        order_item_repo: IOrderItemRepository,
        *,
        uow: IUnitOfWork,
        reconciler: LifecycleReconciler,
        recompute_schedule: ScheduleRecompute | None = None,
    ) -> None:
        self._lots = lot_repo
        self._order_items = order_item_repo
        self._uow = uow
        self._reconciler = reconciler
        self._recompute = recompute_schedule

    async def execute(self, actor: User, lot_id: int, position_id: int) -> None:
        position = await self._lots.get_position_by_id(position_id)
        if not position or position.lot_id != lot_id:
            raise LotPositionNotFoundError(f"Position #{position_id} not found on lot #{lot_id}.")
        # Unassigning deletes a real OrderItem, so it is gated exactly like a
        # sibling lot mutation (write:lots, escalating to manage:lots on a
        # terminal lot). The check runs first, before any deletion.
        lot = found_or_raise(
            await self._lots.get_by_id(lot_id),
            LotPositionNotFoundError,
            f"Lot #{lot_id} not found.",
        )
        LotRules.assert_can_update(actor, lot)
        refusal = lot_position_refusal(
            LifecycleAction.UNASSIGN_EXTERNAL,
            position,
            lot_position_context(position, lot.status),
            actor,
        )
        if refusal is PositionRefusal.KIND:
            raise LotPositionNotAssignableError(f"Position #{position_id} is not assigned.")

        order_item = await self._order_items.get_by_lot_position_id(position_id)
        if not order_item or order_item.canceled_at is not None:
            raise OrderItemNotFoundError(f"No order item linked to position #{position_id}.")

        # The lot, then the line and its order, in one acquisition in the
        # lock order; the line and the position are read again through it.
        self._reconciler.touch_order_items([order_item.id])
        await self._reconciler.lock_touched(also=_the_lot(lot_id))
        locked_lot = await self._lots.get_by_id_for_update(lot_id)
        locked_position = (
            next((p for p in locked_lot.positions if p.id == position_id), None)
            if locked_lot
            else None
        )
        if not locked_lot or not locked_position:
            raise LotPositionNotFoundError(f"Position #{position_id} not found on lot #{lot_id}.")
        position = locked_position
        order_item = await self._order_items.get_by_id_for_update(order_item.id)
        if not order_item or order_item.lot_position_id != position_id:
            raise OrderItemNotFoundError(f"No order item linked to position #{position_id}.")
        refusal = lot_position_refusal(
            LifecycleAction.UNASSIGN_EXTERNAL,
            position,
            lot_position_context(position, locked_lot.status, order_item),
            actor,
        )
        if refusal is PositionRefusal.KIND:
            raise LotPositionNotAssignableError(f"Position #{position_id} is not assigned.")
        if refusal is not None:
            raise LotPositionAlreadyAssignedError(
                f"Order item #{order_item.id} is already {order_item.status.value!r}; "
                f"unassign is only allowed while pending/requested."
            )

        await assert_no_provisions(self._lots, position_id)
        await self._order_items.delete(order_item)
        # The deleted line no longer leads the reconciler to its order and
        # position, so both are registered themselves.
        self._reconciler.touch_orders([order_item.order_id])

        now = now_utc()
        position.changed = now
        position.changes = append_changelog(
            position.changes, actor.full_name, f"Unassigned from order item #{order_item.id}."
        )
        await self._lots.save_position(position)
        self._reconciler.touch_positions([position.id])

        await self._lots.record_event(
            build_lot_event(
                lot_id,
                actor,
                LotEventType.POSITION_UNASSIGNED_EXTERNAL,
                "position",
                f"Position #{position_id} unassigned from order item #{order_item.id}.",
                entity_id=position_id,
                payload={"order_item_id": order_item.id},
            )
        )
        await self._reconciler.run(actor, now)
        await self._uow.commit()
        await recompute_schedule_after_commit(
            self._recompute,
            after=f"unassigning position #{position_id} of lot #{lot_id}; the delete is committed.",
        )
        log.info(f"Unassigned position #{position_id} of lot #{lot_id}.")
