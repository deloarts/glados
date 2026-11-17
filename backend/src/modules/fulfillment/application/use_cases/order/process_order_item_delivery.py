"""Books a delivery and runs the whole fulfillment cascade in one
transaction: the line's delivery row and totals, and through the lifecycle
reconciler the statuses of the line, its order, the demands allocated to it
and, for a MADE line, its lot position, lot and the lot's made demands, with
their events, which drive the notifications.
Only a line that OrderRules.can_deliver accepts takes a delivery.
Deliver-all books every such line of an order in one transaction, so one
failing line books none of them, and skips every other line by the same
rule.

A line that is not a MADE line takes pieces beyond its quantity within its
over-delivery tolerance, and the booking that brings it within its
under-delivery tolerance of its quantity closes it short, as an explicit
close short does (services/delivery_tolerances.py). A booking that sends
pieces back for redelivery leaves the line open, since more is coming.

A MADE line's accepted pieces must fit what its position's upstream made
available, and its pieces lost at receipt close the lot short through the
shared disposition; both are checked and booked before the reconciler runs.

The lot of a MADE line is locked together with the order and the line, and
first, as the one lock order has it, because the reconciler writes the
line's position and lot. A booking that loses pieces on a MADE line locks
the lot alone first and then, with the lines, the lot's production orders
and lines, which the disposition may cut.

The MADE-line steps (the lot check, the disposition of lost pieces and the
lot work a losing booking locks) are in _made_line_delivery.py, the rules of
a booking in domain/services/delivery_booking_rules.py, and deliver-all, which
books through this use case, in deliver_all_order_items.py.
"""

from dataclasses import dataclass
from datetime import datetime

from src.modules.fulfillment.application.dto.order_dto import OrderItemResult
from src.modules.fulfillment.application.mappers.order_mapper import OrderItemMapper
from src.modules.fulfillment.application.services.delivery_tolerances import DeliveryTolerances
from src.modules.fulfillment.application.services.lifecycle_loader import AggregateIds
from src.modules.fulfillment.application.services.lifecycle_reconciler import LifecycleReconciler
from src.modules.fulfillment.application.services.lifecycle_reconciler import ReconcileResult
from src.modules.fulfillment.application.services.piece_disposition import DispositionOutcome
from src.modules.fulfillment.application.services.time_budget_propagation import BudgetOrders
from src.modules.fulfillment.application.services.time_budget_propagation import (
    recompute_time_budgets_of_projects,
)
from src.modules.fulfillment.application.use_cases.order._lines import close_line_short
from src.modules.fulfillment.application.use_cases.order._lines import fit_line_allocations
from src.modules.fulfillment.application.use_cases.order._lines import lots_of_made_lines
from src.modules.fulfillment.application.use_cases.order._made_line_delivery import MadeLineDelivery
from src.modules.fulfillment.application.use_cases.order.deliver_all_order_items import (
    DeliverAllOrderItems,
)
from src.modules.fulfillment.application.use_cases.production_lot.create_lot import CreateLot
from src.modules.fulfillment.application.use_cases.production_schedule.recompute_machine_schedule import (
    RecomputeMachineSchedule,
)
from src.modules.fulfillment.domain.entities.order import Order
from src.modules.fulfillment.domain.entities.order_item import OrderItem
from src.modules.fulfillment.domain.entities.order_item_delivery import OrderItemDelivery
from src.modules.fulfillment.domain.errors import OrderItemNotFoundError
from src.modules.fulfillment.domain.errors import OrderNotFoundError
from src.modules.fulfillment.domain.events.order_events import DeliveryPiecesRejected
from src.modules.fulfillment.domain.events.order_events import OrderItemDelivered
from src.modules.fulfillment.domain.services.delivery_booking_rules import accepted_quantity
from src.modules.fulfillment.domain.services.delivery_booking_rules import booked_storage_place
from src.modules.fulfillment.domain.services.delivery_booking_rules import closes_short_on_booking
from src.modules.fulfillment.domain.services.delivery_booking_rules import fulfilled_bought_demands
from src.modules.fulfillment.domain.services.delivery_booking_rules import loses_made_pieces
from src.modules.fulfillment.domain.services.delivery_booking_rules import record_delivery_on_line
from src.modules.fulfillment.domain.services.delivery_booking_rules import refits_lost_allocations
from src.modules.fulfillment.domain.services.delivery_booking_rules import remaining_to_deliver
from src.modules.fulfillment.domain.services.delivery_tolerance import NO_TOLERANCE
from src.modules.fulfillment.domain.services.delivery_tolerance import DeliveryTolerance
from src.modules.fulfillment.domain.services.delivery_tolerance import over_delivery_allowance
from src.modules.fulfillment.domain.services.order_rules import OrderRules
from src.modules.fulfillment.domain.value_objects.lifecycle_aggregate import LifecycleAggregate
from src.modules.fulfillment.domain.value_objects.material_receipt import MaterialReceipt
from src.modules.fulfillment.domain.value_objects.order_status import OrderLineType
from src.modules.fulfillment.domain.value_objects.rejection_outcome import RejectionOutcome
from src.modules.fulfillment.ports.outbound.repositories.bought_item_demand_repository import (
    IBoughtItemAllocationRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.made_item_demand_repository import (
    IMadeItemAllocationRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.made_item_demand_repository import (
    IMadeItemDemandItemRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.order_repository import (
    IOrderItemDeliveryRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.order_repository import (
    IOrderItemRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.order_repository import IOrderRepository
from src.modules.fulfillment.ports.outbound.repositories.production_lot_repository import (
    IProductionLotRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.production_order_interruption_repository import (
    IProductionOrderInterruptionRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.production_order_repository import (
    IProductionOrderRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.source_item_demand_repository import (
    ISourceItemAllocationRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.source_item_demand_repository import (
    ISourceItemDemandRepository,
)
from src.modules.platform.application.services.lookup import found_or_raise
from src.modules.platform.application.services.schedule_recompute_port import (
    recompute_schedule_after_commit,
)
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.exceptions import ConcurrentModificationError
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.ports.outbound.event_bus_port import IEventBus
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork
from src.modules.workspace.ports.outbound.workspace_queries import IProjectQueries
from src.shared_kernel.domain.events.base import DomainEvent
from src.shared_kernel.domain.services.clock import now_utc

__all__ = [
    "DeliverAllOrderItems",
    "DeliveryBooking",
    "DeliveryEffects",
    "ProcessOrderItemDelivery",
]


@dataclass(frozen=True)
class DeliveryBooking:
    """One booked delivery, kept for the effects that follow the
    reconciler: the pieces of this booking, what the rejected ones become
    and, for pieces lost on a MADE line, the disposition booked with them."""

    order_item_id: int
    delivered_now: float
    quantity_rejected: float = 0.0
    rejection_reason: str | None = None
    rejection_note: str | None = None
    rejection_outcome: str | None = None
    create_replacement: bool = True
    disposition: DispositionOutcome | None = None


@dataclass
class DeliveryEffects:
    """What bookings change outside the order lines, as events to publish in
    booking order, and how many bought demands the run fulfilled."""

    events: list[DomainEvent]
    fulfilled_count: int = 0


class ProcessOrderItemDelivery:
    """Delivery processing for one order item, gated on RECEIVE_DELIVERIES."""

    def __init__(
        self,
        order_item_repo: IOrderItemRepository,
        order_repo: IOrderRepository,
        delivery_repo: IOrderItemDeliveryRepository,
        recompute_schedule: RecomputeMachineSchedule | None = None,
        *,
        event_bus: IEventBus,
        uow: IUnitOfWork,
        lot_repo: IProductionLotRepository,
        made_item_demand_repo: IMadeItemDemandItemRepository,
        made_item_allocation_repo: IMadeItemAllocationRepository,
        source_item_demand_repo: ISourceItemDemandRepository,
        source_item_allocation_repo: ISourceItemAllocationRepository,
        bought_item_allocation_repo: IBoughtItemAllocationRepository,
        production_order_repo: IProductionOrderRepository,
        create_lot: CreateLot,
        reconciler: LifecycleReconciler,
        interruption_repo: IProductionOrderInterruptionRepository,
        delivery_tolerances: DeliveryTolerances | None = None,
        project_repo: IProjectQueries | None = None,
    ) -> None:
        """The production order and interruption repositories are what a
        disposition of pieces lost on a MADE line writes besides the lot,
        and the projects give the time budgets it changes. Without
        `delivery_tolerances` every line takes exactly its quantity."""
        self._projects = project_repo
        self._order_items = order_item_repo
        self._orders = order_repo
        self._deliveries = delivery_repo
        self._recompute = recompute_schedule
        self._bus = event_bus
        self._uow = uow
        self._reconciler = reconciler
        self._lots = lot_repo
        self._source_item_allocations = source_item_allocation_repo
        self._bought_item_allocations = bought_item_allocation_repo
        self._production_orders = production_order_repo
        self._tolerances = delivery_tolerances
        self._made = MadeLineDelivery(
            lots=lot_repo,
            production_orders=production_order_repo,
            order_items=order_item_repo,
            orders=order_repo,
            interruptions=interruption_repo,
            made_item_demands=made_item_demand_repo,
            made_item_allocations=made_item_allocation_repo,
            source_item_demands=source_item_demand_repo,
            source_item_allocations=source_item_allocation_repo,
            bought_item_allocations=bought_item_allocation_repo,
            create_lot=create_lot,
            reconciler=reconciler,
            projects=project_repo,
        )

    async def execute(
        self,
        actor: User,
        order_item_id: int,
        quantity: float | None = None,
        storage_place: str | None = None,
        quantity_rejected: float = 0.0,
        rejection_reason: str | None = None,
        rejection_note: str | None = None,
        rejection_outcome: str | None = None,
        create_replacement: bool = True,
        material: MaterialReceipt | None = None,
    ) -> OrderItemResult:
        """`material` is where the received material comes from, recorded
        on the delivery row for its genealogy."""
        OrderRules.assert_can_receive_delivery(actor)
        now = now_utc()
        line = found_or_raise(
            await self._order_items.get_by_id(order_item_id),
            OrderItemNotFoundError,
            f"Order item #{order_item_id} not found.",
        )
        await self.lock(
            [line],
            with_lot_work=loses_made_pieces(line, quantity_rejected, rejection_outcome),
        )
        booking = await self.book(
            actor,
            order_item_id,
            now,
            locked_order_id=line.order_id,
            quantity=quantity,
            storage_place=storage_place,
            quantity_rejected=quantity_rejected,
            rejection_reason=rejection_reason,
            rejection_note=rejection_note,
            rejection_outcome=rejection_outcome,
            create_replacement=create_replacement,
            material=material,
        )

        result = await self._reconciler.run(actor, now)
        effects = await self.apply_effects(actor, [booking], result)
        for event in effects.events:
            await self._bus.publish(event)

        await self._uow.commit()

        await recompute_schedule_after_commit(
            self._recompute,
            after=(
                f"processing delivery of order item "
                f"#{order_item_id}; the delivery itself is committed."
            ),
        )

        log.info(
            f"Processed delivery of order item #{order_item_id}. "
            f"Fulfilled {effects.fulfilled_count} demand(s)."
        )

        delivered = found_or_raise(
            await self._order_items.get_by_id(order_item_id),
            OrderItemNotFoundError,
            f"Order item #{order_item_id} not found.",
        )
        return OrderItemMapper.to_result(delivered)

    async def lock(self, lines: list[OrderItem], *, with_lot_work: bool = False) -> None:
        """Registers the lines with the reconciler and locks them with their
        orders, and the lots their MADE lines supply, in one acquisition
        before anything is read for the booking. With `with_lot_work`, for a
        booking that loses pieces on a MADE line, the lots come first alone
        and their work joins the lines' acquisition (lot_work_targets)."""
        lots = lots_of_made_lines(lines)
        work = await self.lot_work_targets(lots) if with_lot_work else AggregateIds()
        self._reconciler.touch_order_items([line.id for line in lines])
        await self._reconciler.lock_touched(also=lots.union(work))

    async def lot_work_targets(self, lots: AggregateIds) -> AggregateIds:
        """Locks the lots alone and returns the work of their positions that a
        disposition may cut, for the caller's next acquisition
        (MadeLineDelivery.lot_work_targets)."""
        return await self._made.lot_work_targets(lots)

    async def book(
        self,
        actor: User,
        order_item_id: int,
        now: datetime,
        *,
        locked_order_id: int | None = None,
        quantity: float | None = None,
        storage_place: str | None = None,
        quantity_rejected: float = 0.0,
        rejection_reason: str | None = None,
        rejection_note: str | None = None,
        rejection_outcome: str | None = None,
        create_replacement: bool = True,
        accepted_earlier: dict[int, float] | None = None,
        locked: tuple[Order, OrderItem] | None = None,
        material: MaterialReceipt | None = None,
    ) -> DeliveryBooking:
        """Books one delivery on a line that `lock` locked: the delivery row
        and the line's totals and, for pieces lost on a MADE line, their
        disposition. The statuses follow when the reconciler runs.
        `locked_order_id` is the order `lock` locked with the line, when the
        caller found the line by its id alone. `accepted_earlier` maps a lot
        position to the pieces bookings before this one in the same
        transaction accepted on it, which its stored completed count does not
        hold until the run; a MADE booking adds its own accepted pieces to
        it. `locked` is the order and the line as the caller read them under
        its locks, so a caller booking many lines reads each only once."""
        delivered_now, disposition = await self._record_delivery(
            actor,
            order_item_id,
            quantity,
            storage_place,
            now,
            quantity_rejected,
            rejection_reason,
            rejection_note,
            rejection_outcome,
            create_replacement,
            accepted_earlier,
            locked_order_id,
            locked,
            material,
        )
        return DeliveryBooking(
            order_item_id=order_item_id,
            delivered_now=delivered_now,
            quantity_rejected=quantity_rejected,
            rejection_reason=rejection_reason,
            rejection_note=rejection_note,
            rejection_outcome=rejection_outcome,
            create_replacement=create_replacement,
            disposition=disposition,
        )

    async def apply_effects(
        self, actor: User, bookings: list[DeliveryBooking], result: ReconcileResult
    ) -> DeliveryEffects:
        """What the bookings change outside the order lines, once the
        reconciler has stored the statuses and published their events, the
        demands' included. Returns the events per booking in the order a
        single delivery publishes them: lot, delivery, rejection, and how
        many bought demands the run fulfilled."""
        effects = DeliveryEffects(
            events=[], fulfilled_count=fulfilled_bought_demands(result.changes)
        )
        lines = {
            line.id: line
            for line in await self._order_items.get_by_ids(
                sorted({booking.order_item_id for booking in bookings})
            )
        }
        for booking in bookings:
            line = found_or_raise(
                lines.get(booking.order_item_id),
                OrderItemNotFoundError,
                f"Order item #{booking.order_item_id} not found.",
            )

            if line.line_type == OrderLineType.MADE:
                effects.events.extend(
                    await self._made.delivery_events(actor, line, booking.disposition)
                )
            effects.events.append(
                OrderItemDelivered(
                    order_item_id=line.id,
                    order_id=line.order_id,
                    bought_item_id=line.bought_item_id,
                    actor_id=actor.id,
                    source_item_id=line.source_item_id,
                    quantity=booking.delivered_now,
                )
            )
            if booking.quantity_rejected > 0:
                effects.events.append(
                    DeliveryPiecesRejected(
                        order_item_id=line.id,
                        order_id=line.order_id,
                        supplier_id=line.supplier_id,
                        quantity=booking.quantity_rejected,
                        reason=booking.rejection_reason or "",
                        outcome=booking.rejection_outcome or "",
                        actor_id=actor.id,
                    )
                )
        # Lost pieces shrank their lots; the time budget lock comes after
        # every lifecycle row lock, so this runs last.
        await recompute_time_budgets_of_projects(
            {
                project_id
                for booking in bookings
                if booking.disposition is not None
                for project_id in booking.disposition.project_ids
            },
            self._projects,
            self._lots,
            BudgetOrders(self._production_orders, self._reconciler.lock_plan),
        )
        return effects

    async def can_deliver(self, order: Order, order_item: OrderItem) -> bool:
        """Whether the line can take a delivery under the rule the booking
        enforces, with the lot's status read for a MADE line. Deliver-all
        filters its lines with it."""
        return OrderRules.can_deliver(order, order_item, await self._made.lot_status(order_item))

    async def _fit_allocations_to_what_can_arrive(self, order_item: OrderItem) -> None:
        """Fits the line's allocations into what is left to come once pieces
        were lost at receipt (refits_lost_allocations), and the demands' rest
        opens again (lifecycle/demand.py). The demands are locked with the
        line."""
        bought_ids, source_ids = await fit_line_allocations(
            order_item,
            order_item.allocatable_quantity,
            bought_allocations=self._bought_item_allocations,
            source_allocations=self._source_item_allocations,
        )
        self._reconciler.touch_demands(LifecycleAggregate.BOUGHT_DEMANDS, bought_ids)
        self._reconciler.touch_demands(LifecycleAggregate.SOURCE_DEMANDS, source_ids)

    async def _close_within_tolerance(
        self, actor: User, order_item: OrderItem, tolerance: DeliveryTolerance, now: datetime
    ) -> None:
        """Closes the line short at the pieces it settled, since what it
        still lacks is within its under-delivery tolerance; its allocations
        are fitted into the pieces it delivered and the demands' rest opens
        again, which the demands are locked with the line for."""
        bought_ids, source_ids = await close_line_short(
            order_item,
            actor,
            now,
            cause=f"within the under-delivery tolerance of {tolerance.under_percent:g}%",
            order_items=self._order_items,
            bought_allocations=self._bought_item_allocations,
            source_allocations=self._source_item_allocations,
        )
        self._reconciler.touch_demands(LifecycleAggregate.BOUGHT_DEMANDS, bought_ids)
        self._reconciler.touch_demands(LifecycleAggregate.SOURCE_DEMANDS, source_ids)

    async def _locked_line(
        self,
        order_item_id: int,
        locked_order_id: int | None,
        locked: tuple[Order, OrderItem] | None,
    ) -> tuple[Order, OrderItem]:
        """The line and its order as the booking's locks hold them, read
        again unless the caller passes them in `locked`."""
        # Read through its lock, so concurrent deliveries cannot both pass
        # the overshoot check; a caller that read it under its lock passes it.
        order_item = (
            locked[1]
            if locked is not None
            else found_or_raise(
                await self._order_items.get_by_id_for_update(order_item_id),
                OrderItemNotFoundError,
                f"Order item #{order_item_id} not found.",
            )
        )
        # The locks cover the order the line was on when it was read. A move
        # that committed while this request waited put it on another order,
        # whose lock would come after the line's, so the request is repeated
        # on the current state instead.
        if locked_order_id is not None and order_item.order_id != locked_order_id:
            raise ConcurrentModificationError(
                f"Order item #{order_item_id} was moved to another order while this delivery "
                "was waiting for it. Reload and try again."
            )
        order = (
            locked[0]
            if locked is not None and locked[0].id == order_item.order_id
            else found_or_raise(
                await self._orders.get_by_id(order_item.order_id),
                OrderNotFoundError,
                f"Order #{order_item.order_id} not found.",
            )
        )
        return order, order_item

    async def _record_delivery(
        self,
        actor: User,
        order_item_id: int,
        quantity: float | None,
        storage_place: str | None,
        now: datetime,
        quantity_rejected: float = 0.0,
        rejection_reason: str | None = None,
        rejection_note: str | None = None,
        rejection_outcome: str | None = None,
        create_replacement: bool = True,
        accepted_earlier: dict[int, float] | None = None,
        locked_order_id: int | None = None,
        locked: tuple[Order, OrderItem] | None = None,
        material: MaterialReceipt | None = None,
    ) -> tuple[float, DispositionOutcome | None]:
        """Returns the quantity accepted by this call and, for pieces lost on
        a MADE line, their disposition. Without `quantity`, everything left
        after the rejected pieces is accepted. A MADE line's checks run
        before anything is written."""
        order, order_item = await self._locked_line(order_item_id, locked_order_id, locked)
        OrderRules.assert_can_deliver(order, order_item, await self._made.lot_status(order_item))
        tolerance = (
            await self._tolerances.for_line(order_item)
            if self._tolerances is not None
            else NO_TOLERANCE
        )

        remaining = remaining_to_deliver(order_item)
        delivered_now = accepted_quantity(remaining, quantity, quantity_rejected)
        OrderRules.assert_valid_delivery(
            order_item,
            delivered_now,
            quantity_rejected,
            remaining,
            rejection_reason,
            rejection_outcome,
            allowance=over_delivery_allowance(order_item, tolerance),
        )
        made = await self._made.checked_lot(
            order_item, delivered_now, quantity_rejected, rejection_outcome, accepted_earlier
        )

        storage_place = booked_storage_place(storage_place, order_item)
        receipt = (material or MaterialReceipt()).cleaned()
        await self._deliveries.save(
            OrderItemDelivery(
                id=0,
                order_item_id=order_item_id,
                quantity=delivered_now,
                delivery_date=now,
                storage_place=storage_place,
                receiver_id=actor.id,
                created=now,
                quantity_rejected=quantity_rejected,
                rejection_reason=rejection_reason,
                rejection_note=rejection_note,
                rejection_outcome=(
                    RejectionOutcome(rejection_outcome) if rejection_outcome is not None else None
                ),
                supplier_batch=receipt.supplier_batch,
                delivery_note_number=receipt.delivery_note_number,
                certificate_reference=receipt.certificate_reference,
                damage_noted_on_delivery_note=receipt.damage_noted_on_delivery_note,
            )
        )

        record_delivery_on_line(
            order_item,
            actor,
            now,
            delivered_now=delivered_now,
            quantity_rejected=quantity_rejected,
            rejection_reason=rejection_reason,
            rejection_outcome=rejection_outcome,
            storage_place=storage_place,
        )
        await self._order_items.save(order_item)
        if refits_lost_allocations(order_item, rejection_outcome):
            await self._fit_allocations_to_what_can_arrive(order_item)
        if closes_short_on_booking(order_item, tolerance, rejection_outcome):
            await self._close_within_tolerance(actor, order_item, tolerance, now)

        disposition: DispositionOutcome | None = None
        if made is not None and loses_made_pieces(order_item, quantity_rejected, rejection_outcome):
            lot, position = made
            disposition = await self._made.apply_lost_disposition(
                actor,
                order_item,
                lot,
                position,
                delivered_now,
                quantity_rejected,
                rejection_reason,
                rejection_note,
                create_replacement,
                now,
            )
        return delivered_now, disposition
