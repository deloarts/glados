"""
Corrects a booked delivery by taking back accepted pieces of one delivery
row, for example when goods were counted twice. The delivery rows are never
changed: the correction is a new row with the negative quantity, naming the
row it corrects and the reason, and the line's delivered total drops by the
same amount, so the total stays the sum of the rows. The line's delivery
date follows the rows as well: it is the latest delivery the corrections
left standing, and none once every piece is taken back. The lifecycle
reconciler derives the statuses of the line, its order and the demands
allocated to the line, which may leave DELIVERED again.

Only accepted pieces are corrected, on a partially delivered or delivered
line that is not a MADE line, whose lot keeps the delivered pieces, on an
order that is not canceled and a line that is not closed short, since both
wait for nothing more and would stay open for good; a closed-short line is
reopened first. A correction takes back at most what the row accepted less
what earlier corrections of it took back. A demand the deliveries fulfil
derives back from the corrected total, but the correction is refused while
a demand allocated to the line consumed its pieces: one marked fulfilled by
hand, or a raw material demand whose lot processed pieces at its first
position. A correction that takes back pieces delivered beyond the line's
quantity within its over-delivery tolerance fits the line's allocations into
what it still delivered (_lines.py fit_line_allocations), since the surplus
they drew on is gone. Locking the line locks the demands allocated to it
as well, so the check reads them under their locks and a demand cannot be
marked fulfilled between the check and the commit. It needs the permission to receive
deliveries.

A correction that carries a RejectionAfterReceipt takes the pieces back as
rejected ones instead, for damage found after the goods were accepted: the
row records them in quantity_rejected with their reason, note and outcome,
and the line's rejected totals grow by them as a rejection at receipt would
have booked them (delivery_booking_rules.record_rejection_after_receipt).
Lost pieces never arrive, so the line's allocations are fitted into what it
can still deliver and the demands' rest opens again. Such a correction
publishes DeliveryPiecesRejected, which the rejection at receipt publishes
too; a correction without one records no event of its own.
"""

from src.modules.fulfillment.application.dto.order_dto import OrderItemResult
from src.modules.fulfillment.application.mappers.order_mapper import OrderItemMapper
from src.modules.fulfillment.application.services.lifecycle_reconciler import LifecycleReconciler
from src.modules.fulfillment.application.use_cases.order._lines import fit_line_allocations
from src.modules.fulfillment.application.use_cases.order._lines import lots_of_made_lines
from src.modules.fulfillment.application.use_cases.order._lines import read_order_line
from src.modules.fulfillment.application.use_cases.production_schedule.recompute_machine_schedule import (
    RecomputeMachineSchedule,
)
from src.modules.fulfillment.domain.entities.order_item import OrderItem
from src.modules.fulfillment.domain.entities.order_item_delivery import OrderItemDelivery
from src.modules.fulfillment.domain.entities.order_item_delivery import latest_arrival
from src.modules.fulfillment.domain.errors import OrderItemDeliveryNotFoundError
from src.modules.fulfillment.domain.events.order_events import DeliveryPiecesRejected
from src.modules.fulfillment.domain.services.delivery_booking_rules import (
    record_rejection_after_receipt,
)
from src.modules.fulfillment.domain.services.lot_rules import pieces_processed_at
from src.modules.fulfillment.domain.services.order_rules import OrderRules
from src.modules.fulfillment.domain.value_objects.lifecycle_aggregate import LifecycleAggregate
from src.modules.fulfillment.domain.value_objects.rejection_after_receipt import (
    RejectionAfterReceipt,
)
from src.modules.fulfillment.domain.value_objects.rejection_outcome import RejectionOutcome
from src.modules.fulfillment.ports.outbound.repositories.bought_item_demand_repository import (
    IBoughtItemAllocationRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.bought_item_demand_repository import (
    IBoughtItemDemandItemRepository,
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
from src.modules.fulfillment.ports.outbound.repositories.source_item_demand_repository import (
    ISourceItemAllocationRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.source_item_demand_repository import (
    ISourceItemDemandRepository,
)
from src.modules.platform.application.services.schedule_recompute_port import (
    recompute_schedule_after_commit,
)
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.services.edit_version import assert_edit_version
from src.modules.platform.domain.services.edit_version import bump_edit_version
from src.modules.platform.domain.services.quantities import quantity_gt
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.ports.outbound.event_bus_port import IEventBus
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork
from src.shared_kernel.domain.services.changelog_service import append_changelog
from src.shared_kernel.domain.services.clock import now_utc

# Closes the changelog lines of the statuses a correction moves.
_CORRECTED = "delivery corrected"


class CorrectOrderItemDelivery:
    """Books a correction of one delivery row; see the module docstring."""

    def __init__(
        self,
        order_repo: IOrderRepository,
        order_item_repo: IOrderItemRepository,
        delivery_repo: IOrderItemDeliveryRepository,
        allocation_repo: IBoughtItemAllocationRepository,
        demand_repo: IBoughtItemDemandItemRepository,
        recompute_schedule: RecomputeMachineSchedule | None = None,
        *,
        uow: IUnitOfWork,
        reconciler: LifecycleReconciler,
        source_item_allocation_repo: ISourceItemAllocationRepository | None = None,
        source_item_demand_repo: ISourceItemDemandRepository | None = None,
        lot_repo: IProductionLotRepository | None = None,
        event_bus: IEventBus | None = None,
    ) -> None:
        """Without `event_bus` a rejection after receipt publishes no event."""
        self._bus = event_bus
        self._orders = order_repo
        self._order_items = order_item_repo
        self._deliveries = delivery_repo
        self._allocations = allocation_repo
        self._demands = demand_repo
        self._recompute = recompute_schedule
        self._uow = uow
        self._reconciler = reconciler
        self._source_item_allocations = source_item_allocation_repo
        self._source_item_demands = source_item_demand_repo
        self._lots = lot_repo

    async def execute(
        self,
        actor: User,
        order_id: int,
        order_item_id: int,
        delivery_id: int,
        quantity: float,
        reason: str | None,
        *,
        expected_edit_version: int | None = None,
        rejection: RejectionAfterReceipt | None = None,
    ) -> OrderItemResult:
        """`reason` says why pieces are taken back as a miscount; a correction
        with `rejection` takes them back as rejected ones instead and needs
        no reason."""
        OrderRules.assert_can_receive_delivery(actor)
        OrderRules.assert_correction_explained(order_item_id, reason, rejection)
        _, item = await read_order_line(self._orders, self._order_items, order_id, order_item_id)

        # Locked with its order before anything is checked, so a delivery
        # or another correction booked meanwhile cannot slip past the
        # bounds below.
        self._reconciler.touch_order_items([order_item_id])
        await self._reconciler.lock_touched(also=lots_of_made_lines([item]))
        order, item = await read_order_line(
            self._orders, self._order_items, order_id, order_item_id
        )
        rows = await self._deliveries.get_by_order_item_id(order_item_id)
        row = next((r for r in rows if r.id == delivery_id), None)
        if row is None:
            raise OrderItemDeliveryNotFoundError(
                f"Delivery #{delivery_id} not found on order item #{order_item_id}."
            )
        already_corrected = -sum(r.quantity for r in rows if r.corrects_delivery_id == row.id)
        OrderRules.assert_delivery_correctable(order, item, row, already_corrected, quantity)
        assert_edit_version(item, expected_edit_version, what=f"Order item #{item.id}")
        OrderRules.assert_no_consumed_demand(item, await self._consumed_demands(item))

        now = now_utc()
        await self._deliveries.save(
            OrderItemDelivery(
                id=0,
                order_item_id=order_item_id,
                quantity=-quantity,
                delivery_date=now,
                storage_place=row.storage_place,
                receiver_id=actor.id,
                created=now,
                corrects_delivery_id=row.id,
                correction_reason=None if rejection is not None else reason,
                quantity_rejected=quantity if rejection is not None else 0.0,
                rejection_reason=rejection.reason if rejection is not None else None,
                rejection_note=rejection.note if rejection is not None else None,
                rejection_outcome=rejection.outcome if rejection is not None else None,
            )
        )
        took_surplus = quantity_gt(item.quantity_settled, item.quantity)
        bump_edit_version(item)
        if rejection is not None:
            record_rejection_after_receipt(
                item, actor, now, delivery_id=row.id, quantity=quantity, rejection=rejection
            )
        else:
            item.quantity_delivered -= quantity
            item.changed = now
            item.changes = append_changelog(
                item.changes,
                actor.full_name,
                f"Delivery #{row.id} corrected: took back {quantity:.3f} {item.unit} ({reason}); "
                f"{item.quantity_delivered:.3f}/{item.quantity:.3f} delivered.",
            )
        item.delivery_date = latest_arrival(
            await self._deliveries.get_by_order_item_id(order_item_id)
        )
        await self._order_items.save(item)
        # Lost pieces never arrive, so what the allocations may sum to drops
        # by them, as it drops by surplus pieces a correction takes back.
        loses_pieces = rejection is not None and rejection.outcome == RejectionOutcome.LOST
        if took_surplus or loses_pieces:
            bought_ids, source_ids = await fit_line_allocations(
                item,
                item.allocatable_quantity,
                bought_allocations=self._allocations,
                source_allocations=self._source_item_allocations,
            )
            self._reconciler.touch_demands(LifecycleAggregate.BOUGHT_DEMANDS, bought_ids)
            self._reconciler.touch_demands(LifecycleAggregate.SOURCE_DEMANDS, source_ids)

        await self._reconciler.run(actor, now, reason=_CORRECTED)
        if rejection is not None and self._bus is not None:
            await self._bus.publish(
                DeliveryPiecesRejected(
                    order_item_id=item.id,
                    order_id=item.order_id,
                    supplier_id=item.supplier_id,
                    quantity=quantity,
                    reason=rejection.reason,
                    outcome=rejection.outcome.value,
                    actor_id=actor.id,
                )
            )
        await self._uow.commit()

        await recompute_schedule_after_commit(
            self._recompute,
            after=(
                f"correcting delivery #{delivery_id} of "
                f"order item #{order_item_id}; the correction itself is committed."
            ),
        )

        log.info(
            f"Corrected delivery #{delivery_id} of order item #{order_item_id}: took back "
            f"{quantity:.3f} {item.unit}"
            + (
                f" as rejected ({rejection.reason}, {rejection.outcome.value})."
                if rejection is not None
                else "."
            )
        )
        corrected = await self._order_items.get_by_id(order_item_id)
        return OrderItemMapper.to_result(
            corrected or item,
            delivery_records=await self._deliveries.get_by_order_item_id(order_item_id),
        )

    async def _consumed_demands(self, item: OrderItem) -> list[str]:
        """The demands of both families allocated to the line that consumed
        its pieces, by name, for the refusal; see the module docstring."""
        names: list[str] = []
        for allocation in await self._allocations.get_by_order_item_id(item.id):
            demand = await self._demands.get_by_id(allocation.demand_item_id)
            if demand is not None and demand.fulfilled_manually_at is not None:
                names.append(f"demand #{demand.id}, fulfilled by hand")
        if self._source_item_allocations is None or self._source_item_demands is None:
            return names
        for source in await self._source_item_allocations.get_by_order_item_id(item.id):
            source_demand = await self._source_item_demands.get_by_id(source.demand_item_id)
            if source_demand is None:
                continue
            if source_demand.fulfilled_manually_at is not None:
                names.append(f"source item demand #{source_demand.id}, fulfilled by hand")
            elif await self._lot_started(source_demand.lot_id):
                names.append(f"source item demand #{source_demand.id}, its lot started")
        return names

    async def _lot_started(self, lot_id: int | None) -> bool:
        """Whether the lot processed pieces at its first position, which
        used up its raw material."""
        if self._lots is None or lot_id is None:
            return False
        lot = await self._lots.get_by_id(lot_id)
        if lot is None or not lot.positions:
            return False
        first = min(lot.positions, key=lambda p: p.sequence)
        return quantity_gt(pieces_processed_at(first), 0.0)
