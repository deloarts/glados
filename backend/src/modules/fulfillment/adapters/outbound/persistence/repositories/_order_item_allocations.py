"""
How much of one order item is allocated, counted over both allocation
tables: a bought item demand and a source item demand sourced from the same
bought item can draw on the same bought line, so a line's capacity is only
known from the two tables together. Shared by the bought and the source
item allocation repositories, internal to the persistence layer.
"""

from sqlalchemy import func
from sqlalchemy import select
from sqlalchemy import union_all
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.fulfillment.adapters.outbound.persistence.models.bought_item_allocation_model import (
    BoughtItemAllocationOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.source_item_allocation_model import (
    SourceItemAllocationOrmModel,
)


async def allocated_quantity_on_order_item(db: AsyncSession, order_item_id: int) -> float:
    """The sum of every bought and source item allocation on the order item,
    0.0 when there is none."""
    bought = (
        select(func.coalesce(func.sum(BoughtItemAllocationOrmModel.quantity), 0.0))
        .where(BoughtItemAllocationOrmModel.order_item_id == order_item_id)
        .scalar_subquery()
    )
    source = (
        select(func.coalesce(func.sum(SourceItemAllocationOrmModel.quantity), 0.0))
        .where(SourceItemAllocationOrmModel.order_item_id == order_item_id)
        .scalar_subquery()
    )
    total = await db.scalar(select(bought + source))
    return float(total or 0.0)


async def allocated_quantities_on_order_items(
    db: AsyncSession, order_item_ids: list[int]
) -> dict[int, float]:
    """allocated_quantity_on_order_item for many order items in one query;
    an order item without any allocation maps to 0.0."""
    if not order_item_ids:
        return {}
    rows = union_all(
        select(
            BoughtItemAllocationOrmModel.order_item_id.label("order_item_id"),
            BoughtItemAllocationOrmModel.quantity.label("quantity"),
        ).where(BoughtItemAllocationOrmModel.order_item_id.in_(order_item_ids)),
        select(
            SourceItemAllocationOrmModel.order_item_id.label("order_item_id"),
            SourceItemAllocationOrmModel.quantity.label("quantity"),
        ).where(SourceItemAllocationOrmModel.order_item_id.in_(order_item_ids)),
    ).subquery()
    totals = await db.execute(
        select(rows.c.order_item_id, func.sum(rows.c.quantity)).group_by(rows.c.order_item_id)
    )
    allocated = {order_item_id: 0.0 for order_item_id in order_item_ids}
    for order_item_id, total in totals.all():
        allocated[order_item_id] = float(total or 0.0)
    return allocated
