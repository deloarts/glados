"""Read enrichment of the ProductionLot repository's lots and positions.

A loaded lot carries display fields that live on other aggregates: the
linked order item of every EXTERNAL or MIXED position, the production
orders of every INTERNAL or MIXED position with their interruptions, the
input demand's status and the order item deciding its arrival, and the
lot's origin and follow-up lots. Each enricher fills them for a whole page
in batched queries. LotReadModelMixin holds the enrichers so the repository
keeps calling them on itself with its own session.
"""

from datetime import date as dt

from sqlalchemy import func
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload
from sqlalchemy.orm import selectinload

from src.modules.fulfillment.adapters.outbound.persistence.models.lot_position_provision_model import (
    LotPositionProvisionOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.order_item_model import (
    OrderItemOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.production_lot_model import (
    ProductionLotOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.production_order_interruption_model import (
    ProductionOrderInterruptionOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.production_order_model import (
    ProductionOrderOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.source_item_allocation_model import (
    SourceItemAllocationOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.source_item_demand_item_model import (
    SourceItemDemandItemOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.production_order_repository import (
    interruption_orm_to_entity,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.production_order_repository import (
    order_orm_to_entity,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.production_order_repository import (
    production_order_load_options,
)
from src.modules.fulfillment.domain.entities.lot_position import EarlierOrderLine
from src.modules.fulfillment.domain.entities.lot_position import LotPosition
from src.modules.fulfillment.domain.entities.production_lot import FollowUpLotSummary
from src.modules.fulfillment.domain.entities.production_lot import ProductionLot
from src.modules.fulfillment.domain.entities.production_order_interruption import (
    ProductionOrderInterruption,
)
from src.modules.fulfillment.domain.value_objects.lot_origin_disposition import LotOriginDisposition
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionKind
from src.modules.fulfillment.domain.value_objects.order_status import OrderItemStatus
from src.modules.fulfillment.domain.value_objects.source_item_demand_status import (
    SourceItemDemandStatus,
)
from src.modules.platform.adapters.outbound.persistence.models.user_model import UserOrmModel

# Sorts undated order items below any dated sibling while still picking
# them when nothing else exists.
_NO_DATE = dt.min


def _order_item_arrival_sort_key(order_item: OrderItemOrmModel) -> tuple[int, dt]:
    """Ranks a demand's order items by arrival: a confirmed delivery beats a
    projection, and within each the latest date wins, because it decides
    when everything is there.
    """
    if order_item.delivery_date is not None:
        return (1, order_item.delivery_date)
    return (0, order_item.expected_delivery_date or _NO_DATE)


class LotReadModelMixin:
    """The repository's read enrichment, mixed into
    SqlAlchemyProductionLotRepository, which provides the session."""

    _db: AsyncSession

    async def _enrich_lots_with_position_info(self, lots: list[ProductionLot]) -> None:
        """Runs both position enrichers over the whole page at once."""
        positions = [position for lot in lots for position in lot.positions]
        if not positions:
            return
        await self._enrich_positions_with_order_info(positions)
        await self._enrich_positions_with_production_orders(positions)

    async def _enrich_positions_with_order_info(
        self, positions: list[LotPosition], *, refresh: bool = False
    ) -> None:
        """Copies the linked order item's fields onto every EXTERNAL or MIXED
        position. Only a live line counts: a canceled one no longer supplies
        the position, which can then be planned again. Of several live lines
        the newest is copied, what the earlier ones, closed short, hold is
        summed, and they are listed newest first. With refresh, order
        items the session already holds are re-read (populate_existing), as
        the locked read needs."""
        position_ids = [
            p.id
            for p in positions
            if p.kind in (LotPositionKind.EXTERNAL.value, LotPositionKind.MIXED.value)
        ]
        if not position_ids:
            return
        rows = (
            await self._db.scalars(
                select(OrderItemOrmModel)
                # Eager-loaded, or reading them would query per row.
                .options(
                    joinedload(OrderItemOrmModel.order),
                    joinedload(OrderItemOrmModel.supplier),
                    joinedload(OrderItemOrmModel.orderer).selectinload(UserOrmModel.members),
                    joinedload(OrderItemOrmModel.creator).selectinload(UserOrmModel.members),
                    selectinload(OrderItemOrmModel.delivery_records),
                )
                .where(
                    OrderItemOrmModel.lot_position_id.in_(position_ids),
                    OrderItemOrmModel.canceled_at.is_(None),
                )
                .execution_options(populate_existing=refresh)
            )
        ).all()
        # The newest live line is the position's line; the earlier ones were
        # closed short and count only with what they hold.
        by_position_id: dict[int | None, OrderItemOrmModel] = {}
        closed: dict[int | None, tuple[float, float]] = {}
        earlier_lines: dict[int | None, list[EarlierOrderLine]] = {}
        for row in sorted(rows, key=lambda r: r.id):
            earlier = by_position_id.get(row.lot_position_id)
            if earlier is not None:
                quantity, delivered = closed.get(row.lot_position_id, (0.0, 0.0))
                closed[row.lot_position_id] = (
                    quantity + earlier.quantity,
                    delivered + earlier.quantity_delivered,
                )
                earlier_lines.setdefault(row.lot_position_id, []).insert(
                    0, self._earlier_order_line(earlier)
                )
            by_position_id[row.lot_position_id] = row
        for position in positions:
            order_item = by_position_id.get(position.id)
            if order_item:
                self._apply_order_item_to_position(position, order_item)
                position.closed_lines_quantity, position.closed_lines_delivered = closed.get(
                    position.id, (0.0, 0.0)
                )
            position.earlier_order_lines = earlier_lines.get(position.id, [])
        provisioned = dict(
            (
                await self._db.execute(
                    select(
                        LotPositionProvisionOrmModel.lot_position_id,
                        func.sum(LotPositionProvisionOrmModel.quantity),
                    )
                    .where(LotPositionProvisionOrmModel.lot_position_id.in_(position_ids))
                    .group_by(LotPositionProvisionOrmModel.lot_position_id)
                )
            )
            .tuples()
            .all()
        )
        for position in positions:
            position.provisioned_quantity = float(provisioned.get(position.id) or 0.0)

    @staticmethod
    def _earlier_order_line(order_item: OrderItemOrmModel) -> EarlierOrderLine:
        """The display fields of a position's line older than its newest."""
        return EarlierOrderLine(
            order_item_id=order_item.id,
            order_id=order_item.order_id,
            order_number=order_item.order.order_number if order_item.order else "",
            supplier_name=order_item.supplier_name or "",
            quantity=order_item.quantity,
            quantity_delivered=order_item.quantity_delivered,
            unit=order_item.unit,
            closed_short=order_item.closed_short_at is not None,
        )

    @staticmethod
    def _apply_order_item_to_position(position: LotPosition, order_item: OrderItemOrmModel) -> None:
        """Copies the linked order item's fields onto a position."""
        position.order_item_id = order_item.id
        position.order_id = order_item.order_id
        position.order_number = order_item.order.order_number if order_item.order else ""
        position.supplier_name = order_item.supplier_name or ""
        position.order_item_supplier_id = order_item.supplier_id
        position.order_item_supplier_external_lead_time_days = (
            order_item.supplier.external_lead_time_days if order_item.supplier else None
        )
        position.order_item_status = OrderItemStatus(order_item.status)
        position.order_item_closed_short = order_item.closed_short_at is not None
        position.expected_delivery_date = order_item.expected_delivery_date
        position.order_item_quantity = order_item.quantity
        position.order_item_quantity_delivered = order_item.quantity_delivered
        position.order_item_delivery_date = order_item.delivery_date
        position.order_item_expected_pickup_date = order_item.expected_pickup_date
        position.order_item_ready_for_pickup_date = order_item.ready_for_pickup_date
        position.order_item_delivery_record_count = len(order_item.delivery_records)
        position.order_item_unit = order_item.unit
        position.order_item_items_per_unit = order_item.items_per_unit
        position.order_item_edit_version = order_item.edit_version
        position.order_item_ordered_by_name = (
            order_item.orderer.full_name
            if order_item.orderer
            else (order_item.creator.full_name if order_item.creator else None)
        )

    async def _enrich_positions_with_production_orders(
        self, positions: list[LotPosition], *, refresh: bool = False
    ) -> None:
        """Attaches the production orders of every position, each with its
        interruptions as the order repository reads them, because the
        schedule explanations anchor a resumed order at its latest resume.
        A position whose orders all ended keeps them too, since their
        completion rows are the position's progress (lot_rules.has_progress).
        With refresh, rows the session already holds are re-read
        (populate_existing), as the locked read needs."""
        position_ids = [p.id for p in positions]
        if not position_ids:
            return
        rows = (
            await self._db.scalars(
                select(ProductionOrderOrmModel)
                .where(ProductionOrderOrmModel.lot_position_id.in_(position_ids))
                .options(*production_order_load_options())
                .order_by(ProductionOrderOrmModel.queue_sequence)
                .execution_options(populate_existing=refresh)
            )
        ).all()
        interruptions_by_order_id = await self._interruptions_by_order_id(
            [row.id for row in rows], refresh=refresh
        )
        by_position_id: dict[int, list[ProductionOrderOrmModel]] = {}
        for row in rows:
            by_position_id.setdefault(row.lot_position_id, []).append(row)
        for position in positions:
            orders = [order_orm_to_entity(r) for r in by_position_id.get(position.id, [])]
            for order in orders:
                order.interruptions = interruptions_by_order_id.get(order.id, [])
            position.production_orders = orders

    async def _interruptions_by_order_id(
        self, order_ids: list[int], *, refresh: bool = False
    ) -> dict[int, list[ProductionOrderInterruption]]:
        """The interruptions of the given orders in one query, oldest first
        per order."""
        if not order_ids:
            return {}
        rows = (
            await self._db.scalars(
                select(ProductionOrderInterruptionOrmModel)
                .where(ProductionOrderInterruptionOrmModel.production_order_id.in_(order_ids))
                .order_by(ProductionOrderInterruptionOrmModel.id)
                .execution_options(populate_existing=refresh)
            )
        ).all()
        by_order_id: dict[int, list[ProductionOrderInterruption]] = {}
        for row in rows:
            by_order_id.setdefault(row.production_order_id, []).append(
                interruption_orm_to_entity(row)
            )
        return by_order_id

    async def _enrich_lots_with_demand_info(
        self, lots: list[ProductionLot], *, refresh: bool = False
    ) -> None:
        """Fills each lot's demand status and source order block in one
        batched pass. With refresh, rows the session already holds are
        re-read (populate_existing), as the locked read needs."""
        demand_ids = [lot.input_demand_id for lot in lots if lot.input_demand_id is not None]
        if not demand_ids:
            return
        demands = (
            await self._db.scalars(
                select(SourceItemDemandItemOrmModel)
                .where(SourceItemDemandItemOrmModel.id.in_(demand_ids))
                .execution_options(populate_existing=refresh)
            )
        ).all()
        demand_by_id = {d.id: d for d in demands}
        source_order_by_demand_id = await self._source_order_info_by_demand_id(
            demand_ids, refresh=refresh
        )
        for lot in lots:
            if lot.input_demand_id is None:
                continue
            demand = demand_by_id.get(lot.input_demand_id)
            if demand is None:
                continue
            lot.demand_status = SourceItemDemandStatus(demand.status)
            source_order = source_order_by_demand_id.get(lot.input_demand_id)
            if source_order is None:
                continue
            lot.source_order_id = source_order.order_id
            lot.source_order_number = (
                source_order.order.order_number if source_order.order else None
            )
            lot.source_expected_delivery_date = source_order.expected_delivery_date
            lot.source_delivery_date = source_order.delivery_date

    async def _enrich_lots_with_lineage_info(self, lots: list[ProductionLot]) -> None:
        """Fills origin and follow-up lots for the whole page."""
        origin_ids = {lot.origin_lot_id for lot in lots if lot.origin_lot_id is not None}
        this_page_ids = [lot.id for lot in lots]

        origin_lot_numbers: dict[int, str] = {}
        if origin_ids:
            origin_rows = (
                await self._db.execute(
                    select(ProductionLotOrmModel.id, ProductionLotOrmModel.lot_number).where(
                        ProductionLotOrmModel.id.in_(origin_ids)
                    )
                )
            ).all()
            origin_lot_numbers = {row.id: row.lot_number for row in origin_rows}

        follow_ups_by_origin_id: dict[int, list[FollowUpLotSummary]] = {}
        if this_page_ids:
            follow_up_rows = (
                await self._db.execute(
                    select(
                        ProductionLotOrmModel.id,
                        ProductionLotOrmModel.lot_number,
                        ProductionLotOrmModel.origin_lot_id,
                        ProductionLotOrmModel.origin_disposition,
                        ProductionLotOrmModel.quantity,
                    ).where(ProductionLotOrmModel.origin_lot_id.in_(this_page_ids))
                )
            ).all()
            for row in follow_up_rows:
                follow_ups_by_origin_id.setdefault(row.origin_lot_id, []).append(
                    FollowUpLotSummary(
                        id=row.id,
                        lot_number=row.lot_number,
                        disposition=LotOriginDisposition(row.origin_disposition),
                        quantity=row.quantity,
                    )
                )

        for lot in lots:
            if lot.origin_lot_id is not None:
                lot.origin_lot_number = origin_lot_numbers.get(lot.origin_lot_id, "")
            lot.follow_up_lots = follow_ups_by_origin_id.get(lot.id, [])

    async def _source_order_info_by_demand_id(
        self, demand_ids: list[int], *, refresh: bool = False
    ) -> dict[int, OrderItemOrmModel]:
        """The order item deciding each demand's arrival, in two queries.
        Stock allocations drop out, so a stock-fulfilled demand has none.
        With refresh, rows the session already holds are re-read."""
        allocations = (
            await self._db.scalars(
                select(SourceItemAllocationOrmModel)
                .where(SourceItemAllocationOrmModel.demand_item_id.in_(demand_ids))
                .execution_options(populate_existing=refresh)
            )
        ).all()
        order_item_ids = [a.order_item_id for a in allocations if a.order_item_id is not None]
        if not order_item_ids:
            return {}

        order_items = (
            await self._db.scalars(
                select(OrderItemOrmModel)
                .where(OrderItemOrmModel.id.in_(order_item_ids))
                .options(selectinload(OrderItemOrmModel.order))
                .execution_options(populate_existing=refresh)
            )
        ).all()
        order_item_by_id = {oi.id: oi for oi in order_items}

        candidates_by_demand_id: dict[int, list[OrderItemOrmModel]] = {}
        for allocation in allocations:
            if allocation.order_item_id is None:
                continue
            order_item = order_item_by_id.get(allocation.order_item_id)
            if order_item is None:
                continue
            candidates_by_demand_id.setdefault(allocation.demand_item_id, []).append(order_item)

        return {
            demand_id: max(candidates, key=_order_item_arrival_sort_key)
            for demand_id, candidates in candidates_by_demand_id.items()
        }

    # ── Steps ────────────────────────────────────────────────────────
