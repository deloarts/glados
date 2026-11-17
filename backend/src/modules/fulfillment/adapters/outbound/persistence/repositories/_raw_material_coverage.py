"""
Shared helper for the source-item-as-virtual-predecessor mechanism (wired up
via ProductionLot.input_demand_id -> SourceItemDemandItem): how much of a
linked demand has actually arrived. Since source item demands are
pooled (SourceItemDemandAllocation, many order items per demand and vice
versa, plus stock-only fulfillment), "arrived" is the delivered pieces that
reach the demand's allocations in the fill of their lines plus
fulfilled_from_stock, the same math allocation_coverage.compute_coverage_totals
does for the demand tables and the demand derivation does for the status,
just queried directly against the ORM here (cheaper than round-tripping
through the full domain-entity mappers for a single float). Only accepted
pieces count; a piece lost at receipt never arrived. Every allocation on the
lines is read, of bought item demands too, which come first in the fill.
Not part of either repository's public port, internal to the persistence
layer. Used by SqlAlchemyProductionLotRepository (completion-recording cap)
and SqlAlchemyProductionOrderRepository (the "waiting on raw material"
display flag).
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.catalogue.domain.value_objects.bought_item_status import AllocationSource
from src.modules.fulfillment.adapters.outbound.persistence.models.bought_item_allocation_model import (
    BoughtItemAllocationOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.order_item_model import (
    OrderItemOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.source_item_allocation_model import (
    SourceItemAllocationOrmModel,
)
from src.modules.fulfillment.domain.services.allocation_coverage import CoverageInfo
from src.modules.fulfillment.domain.services.allocation_coverage import compute_coverage_totals
from src.modules.fulfillment.domain.services.allocation_coverage import fill_by_reference
from src.modules.fulfillment.domain.services.lifecycle.demand import BOUGHT_FILL_RANK
from src.modules.fulfillment.domain.services.lifecycle.demand import SOURCE_FILL_RANK
from src.modules.fulfillment.domain.value_objects.order_status import OrderItemStatus
from src.modules.fulfillment.domain.value_objects.source_item_demand_status import (
    SourceItemAllocationSource,
)

_PLACED_ORDER_ITEM_STATUSES = {
    OrderItemStatus.ORDERED.value,
    OrderItemStatus.PARTIALLY_DELIVERED.value,
    OrderItemStatus.DELIVERED.value,
}


class _AllocationRow:
    """Adapts an allocation ORM row of either family to the protocol of
    compute_coverage_totals and fill_by_reference."""

    def __init__(self, orm: SourceItemAllocationOrmModel | BoughtItemAllocationOrmModel) -> None:
        self.demand_item_id = orm.demand_item_id
        self.quantity = orm.quantity
        self.source = orm.source
        self._order_item_id = orm.order_item_id

    @property
    def coverage_ref_id(self) -> int | None:
        return self._order_item_id


class _OrmOrderItemCoverageSource:
    """Order-item-backed coverage adapter reading straight off ORM rows,
    cheaper than the full order_item_orm_to_entity mapper for this one
    float, which doesn't need creator/project/etc joins. The accepted pieces
    of a line arrived; a canceled line brings none."""

    def __init__(self, order_items_by_id: dict[int, OrderItemOrmModel]) -> None:
        self._order_items_by_id = order_items_by_id

    def coverage_for(self, ref_id: int) -> CoverageInfo | None:
        order_item = self._order_items_by_id.get(ref_id)
        if order_item is None:
            return None
        canceled = order_item.status == OrderItemStatus.CANCELED.value
        return CoverageInfo(
            is_placed=order_item.status in _PLACED_ORDER_ITEM_STATUSES,
            arrived=0.0 if canceled else order_item.quantity_delivered,
        )


async def compute_raw_material_arrived_quantity(db: AsyncSession, demand_id: int) -> float:
    """compute_raw_material_arrived_quantities for one demand, 0.0 if it has
    no allocation yet."""
    return (await compute_raw_material_arrived_quantities(db, [demand_id]))[demand_id]


async def compute_raw_material_arrived_quantities(
    db: AsyncSession, demand_ids: list[int]
) -> dict[int, float]:
    """The arrived quantity of each demand in a few queries instead of
    several per demand. Every requested id has an entry, 0.0 when no
    allocation exists for it yet."""
    result: dict[int, float] = {demand_id: 0.0 for demand_id in demand_ids}
    if not demand_ids:
        return result
    allocation_rows = (
        await db.scalars(
            select(SourceItemAllocationOrmModel)
            .where(SourceItemAllocationOrmModel.demand_item_id.in_(demand_ids))
            .order_by(SourceItemAllocationOrmModel.id)
        )
    ).all()
    if not allocation_rows:
        return result

    allocations_by_demand: dict[int, list[_AllocationRow]] = {}
    for row in allocation_rows:
        allocations_by_demand.setdefault(row.demand_item_id, []).append(_AllocationRow(row))
    order_item_ids = sorted(
        {r.order_item_id for r in allocation_rows if r.order_item_id is not None}
    )
    order_items_by_id: dict[int, OrderItemOrmModel] = {}
    fill = {}
    if order_item_ids:
        rows = (
            await db.scalars(
                select(OrderItemOrmModel).where(OrderItemOrmModel.id.in_(order_item_ids))
            )
        ).all()
        order_items_by_id = {r.id: r for r in rows}
        on_lines_bought = (
            await db.scalars(
                select(BoughtItemAllocationOrmModel).where(
                    BoughtItemAllocationOrmModel.order_item_id.in_(order_item_ids)
                )
            )
        ).all()
        on_lines_source = (
            await db.scalars(
                select(SourceItemAllocationOrmModel).where(
                    SourceItemAllocationOrmModel.order_item_id.in_(order_item_ids)
                )
            )
        ).all()
        fill = fill_by_reference(
            (
                BOUGHT_FILL_RANK,
                [_AllocationRow(r) for r in on_lines_bought],
                AllocationSource.STOCK.value,
            ),
            (
                SOURCE_FILL_RANK,
                [_AllocationRow(r) for r in on_lines_source],
                SourceItemAllocationSource.STOCK.value,
            ),
        )

    coverage = _OrmOrderItemCoverageSource(order_items_by_id)
    for demand_id, allocations in allocations_by_demand.items():
        _, _, delivered, fulfilled_from_stock = compute_coverage_totals(
            allocations,
            coverage,
            SourceItemAllocationSource.STOCK.value,
            rank=SOURCE_FILL_RANK,
            fill=fill,
        )
        result[demand_id] = delivered + fulfilled_from_stock
    return result
