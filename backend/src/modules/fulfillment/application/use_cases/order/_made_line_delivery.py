"""The MADE-line side of booking a delivery.

A MADE line carries the pieces of a lot position, so its booking reads the
lot under the booking's locks and checks the pieces against it, closes the
lot short through the shared disposition when pieces are lost at receipt,
and reports the delivery its position recorded once the reconciler ran. A
booking that loses pieces also locks the lot's work first. The rules these
steps apply are in domain/services/delivery_booking_rules.py and
lot_rules.py. ProcessOrderItemDelivery builds a MadeLineDelivery from its own
repositories.
"""

from datetime import datetime

from src.modules.fulfillment.application.services.lifecycle_loader import AggregateIds
from src.modules.fulfillment.application.services.lifecycle_reconciler import LifecycleReconciler
from src.modules.fulfillment.application.services.lot_cascades import lot_work_lock_targets
from src.modules.fulfillment.application.services.piece_disposition import DispositionOutcome
from src.modules.fulfillment.application.services.piece_disposition import DispositionRepositories
from src.modules.fulfillment.application.services.piece_disposition import apply_disposition
from src.modules.fulfillment.application.services.time_budget_propagation import budget_order_locks
from src.modules.fulfillment.application.use_cases.production_lot.create_lot import CreateLot
from src.modules.fulfillment.domain.entities.lot_position import LotPosition
from src.modules.fulfillment.domain.entities.order_item import OrderItem
from src.modules.fulfillment.domain.entities.production_lot import ProductionLot
from src.modules.fulfillment.domain.events.lot_events import LotPositionDeliveryRecorded
from src.modules.fulfillment.domain.services.delivery_booking_rules import assert_made_booking_fits
from src.modules.fulfillment.domain.services.delivery_booking_rules import draws_on_raw_material
from src.modules.fulfillment.domain.services.delivery_booking_rules import supplying_position_id
from src.modules.fulfillment.domain.services.lot_event_service import build_lot_event
from src.modules.fulfillment.domain.value_objects.lifecycle_aggregate import LifecycleAggregate
from src.modules.fulfillment.domain.value_objects.lot_event_type import LotEventType
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
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.services.quantities import quantity_gt
from src.modules.workspace.ports.outbound.workspace_queries import IProjectQueries
from src.shared_kernel.domain.events.base import DomainEvent


class MadeLineDelivery:
    """The lot reads, checks and writes of a booking on a MADE line."""

    def __init__(
        self,
        *,
        lots: IProductionLotRepository,
        production_orders: IProductionOrderRepository,
        order_items: IOrderItemRepository,
        orders: IOrderRepository,
        interruptions: IProductionOrderInterruptionRepository,
        made_item_demands: IMadeItemDemandItemRepository,
        made_item_allocations: IMadeItemAllocationRepository,
        source_item_demands: ISourceItemDemandRepository,
        source_item_allocations: ISourceItemAllocationRepository,
        bought_item_allocations: IBoughtItemAllocationRepository,
        create_lot: CreateLot,
        reconciler: LifecycleReconciler,
        projects: IProjectQueries | None,
    ) -> None:
        self._lots = lots
        self._production_orders = production_orders
        self._order_items = order_items
        self._orders = orders
        self._interruptions = interruptions
        self._made_item_demands = made_item_demands
        self._made_item_allocations = made_item_allocations
        self._source_item_demands = source_item_demands
        self._source_item_allocations = source_item_allocations
        self._bought_item_allocations = bought_item_allocations
        self._create_lot = create_lot
        self._reconciler = reconciler
        self._projects = projects

    async def lot_work_targets(self, lots: AggregateIds) -> AggregateIds:
        """Locks the lots alone and returns the production orders and live
        lines of their positions with the lines' orders, which a disposition
        may cut, for the caller to lock in its next acquisition; the lock
        order puts every production order before any order or line. The
        queued and paused orders of the lots' projects are among them, since
        the time budget recompute after a disposition may snapshot them
        again."""
        lot_ids = sorted(lots.get(LifecycleAggregate.LOTS))
        if not lot_ids:
            return AggregateIds()
        await self._reconciler.lock_touched(also=lots)
        targets = AggregateIds()
        project_ids: set[int] = set()
        for lot in await self._lots.get_by_ids(lot_ids, refresh=True):
            project_ids.add(lot.project_id)
            targets = targets.union(
                await lot_work_lock_targets(
                    self._reconciler, lot, self._production_orders, self._order_items
                )
            )
        if self._projects is not None:
            targets = targets.union(
                await budget_order_locks(project_ids, self._lots, self._production_orders)
            )
        return targets

    async def lot_status(self, order_item: OrderItem) -> str | None:
        """The status of the lot a MADE line supplies, None for any other
        line."""
        position_id = supplying_position_id(order_item)
        if position_id is None:
            return None
        position = await self._lots.get_position_by_id(position_id)
        if position is None:
            return None
        lot = await self._lots.get_by_id(position.lot_id)
        return lot.status if lot is not None else None

    async def checked_lot(
        self,
        order_item: OrderItem,
        delivered_now: float,
        quantity_rejected: float,
        rejection_outcome: str | None,
        accepted_earlier: dict[int, float] | None = None,
    ) -> tuple[ProductionLot, LotPosition] | None:
        """For a MADE line, the lot and the lot's own object for the line's
        position, read under the lock the booking took and checked with
        assert_made_booking_fits; None for any other line. The pieces
        in `accepted_earlier` (see ProcessOrderItemDelivery.book) count as
        completed, and this booking's accepted pieces are added to them."""
        position_id = supplying_position_id(order_item)
        if position_id is None:
            return None
        found = await self._lots.get_position_by_id(position_id)
        lot = await self._lots.get_by_id_for_update(found.lot_id) if found else None
        position = next((p for p in lot.positions if p.id == position_id), None) if lot else None
        if lot is None or position is None:
            return None
        raw_material_arrived = None
        if quantity_gt(delivered_now, 0.0) and draws_on_raw_material(lot, position):
            raw_material_arrived = (
                await self._lots.get_raw_material_arrived_quantity(lot.input_demand_id)
                if lot.input_demand_id is not None
                else 0.0
            )
        assert_made_booking_fits(
            order_item,
            lot,
            position,
            delivered_now=delivered_now,
            quantity_rejected=quantity_rejected,
            rejection_outcome=rejection_outcome,
            accepted_earlier=accepted_earlier,
            raw_material_arrived=raw_material_arrived,
        )
        if accepted_earlier is not None:
            accepted_earlier[position.id] = accepted_earlier.get(position.id, 0.0) + delivered_now
        return lot, position

    async def apply_lost_disposition(
        self,
        actor: User,
        order_item: OrderItem,
        lot: ProductionLot,
        position: LotPosition,
        delivered_now: float,
        quantity_rejected: float,
        rejection_reason: str | None,
        rejection_note: str | None,
        create_replacement: bool,
        now: datetime,
    ) -> DispositionOutcome:
        """Lost pieces on a MADE line close the lot short through the shared
        disposition, run against the line's position; the delivery record
        carries the scrap facts."""
        closing_event = build_lot_event(
            lot.id,
            actor,
            LotEventType.PIECES_LOST_AT_RECEIPT,
            "lot",
            f"{quantity_rejected:.3f} piece(s) lost at goods receipt on order item "
            f"#{order_item.id} ({rejection_reason}); quantity now "
            f"{lot.quantity - quantity_rejected:.3f}.",
            entity_id=order_item.id,
            payload={
                "order_item_id": order_item.id,
                "position_id": position.id,
                "quantity": quantity_rejected,
                "reason": rejection_reason,
                "note": rejection_note,
            },
        )
        return await apply_disposition(
            lots_repo=self._lots,
            work=self._disposition_work(),
            made_item_demand_repo=self._made_item_demands,
            made_item_allocation_repo=self._made_item_allocations,
            create_lot=self._create_lot,
            actor=actor,
            lot=lot,
            position=position,
            removed_quantity=quantity_rejected,
            quantity_rework=0.0,
            quantity_scrap=quantity_rejected,
            create_replacement=create_replacement,
            closing_event=closing_event,
            replacement_note=f"Replacement for {quantity_rejected:.3f} piece(s) lost at goods "
            f"receipt on order item #{order_item.id} ({rejection_reason}).",
            accepted_now=delivered_now,
            replacement_required_delivery_date=lot.required_delivery_date,
            replacement_priority=lot.priority,
            now=now,
        )

    async def delivery_events(
        self, actor: User, order_item: OrderItem, disposition: DispositionOutcome | None
    ) -> list[DomainEvent]:
        """A MADE line's delivery as its position recorded it, read after
        the reconciler's run, then the events of its lost pieces'
        disposition."""
        if order_item.lot_position_id is None:
            return []
        position = await self._lots.get_position_by_id(order_item.lot_position_id)
        if not position:
            return []
        return [
            LotPositionDeliveryRecorded(
                lot_id=position.lot_id,
                position_id=position.id,
                order_item_id=order_item.id,
                quantity_completed=position.quantity_completed,
                actor_id=actor.id,
            ),
            *(disposition or DispositionOutcome()).events,
        ]

    def _disposition_work(self) -> DispositionRepositories:
        """What the disposition of lost pieces writes besides the lot."""
        return DispositionRepositories(
            production_orders=self._production_orders,
            order_items=self._order_items,
            orders=self._orders,
            interruptions=self._interruptions,
            source_item_demands=self._source_item_demands,
            source_item_allocations=self._source_item_allocations,
            reconciler=self._reconciler,
            bought_allocations=self._bought_item_allocations,
        )
