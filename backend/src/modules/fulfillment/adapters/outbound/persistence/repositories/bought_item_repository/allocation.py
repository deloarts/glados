"""
Concrete SQLAlchemy implementation for the BoughtItemDemandAllocation aggregate.
"""

from sqlalchemy import func
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.catalogue.domain.value_objects.bought_item_status import AllocationSource
from src.modules.fulfillment.adapters.outbound.persistence.models.bought_item_allocation_model import (
    BoughtItemAllocationOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories._order_item_allocations import (
    allocated_quantities_on_order_items,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories._order_item_allocations import (
    allocated_quantity_on_order_item,
)
from src.modules.fulfillment.domain.entities.bought_item_allocation import (
    BoughtItemDemandAllocation,
)


def _orm_to_entity(orm: BoughtItemAllocationOrmModel) -> BoughtItemDemandAllocation:
    return BoughtItemDemandAllocation(
        demand_item_id=orm.demand_item_id,
        order_item_id=orm.order_item_id,
        quantity=orm.quantity,
        source=AllocationSource(orm.source),
        substitute_item_id=orm.substitute_item_id,
        substitute_reason=orm.substitute_reason,
        created_by_id=orm.created_by_id,
        created_at=orm.created_at,
        changed_at=orm.changed_at,
    )


# ══════════════════════════════════════════════════════════════════════
# Allocation repository
# ══════════════════════════════════════════════════════════════════════


class SqlAlchemyBoughtItemAllocationRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def get_by_demand_item_id(self, demand_item_id: int) -> list[BoughtItemDemandAllocation]:
        rows = (
            await self._db.scalars(
                select(BoughtItemAllocationOrmModel).where(
                    BoughtItemAllocationOrmModel.demand_item_id == demand_item_id
                )
            )
        ).all()
        return [_orm_to_entity(r) for r in rows]

    async def get_by_demand_item_ids(
        self, demand_item_ids: list[int], *, refresh: bool = False
    ) -> list[BoughtItemDemandAllocation]:
        if not demand_item_ids:
            return []
        rows = (
            await self._db.scalars(
                select(BoughtItemAllocationOrmModel)
                .where(BoughtItemAllocationOrmModel.demand_item_id.in_(demand_item_ids))
                .execution_options(populate_existing=refresh)
            )
        ).all()
        return [_orm_to_entity(r) for r in rows]

    async def get_by_order_item_id(self, order_item_id: int) -> list[BoughtItemDemandAllocation]:
        rows = (
            await self._db.scalars(
                select(BoughtItemAllocationOrmModel).where(
                    BoughtItemAllocationOrmModel.order_item_id == order_item_id
                )
            )
        ).all()
        return [_orm_to_entity(r) for r in rows]

    async def get_by_order_item_ids(
        self, order_item_ids: list[int], *, refresh: bool = False
    ) -> list[BoughtItemDemandAllocation]:
        if not order_item_ids:
            return []
        rows = (
            await self._db.scalars(
                select(BoughtItemAllocationOrmModel)
                .where(BoughtItemAllocationOrmModel.order_item_id.in_(order_item_ids))
                .execution_options(populate_existing=refresh)
            )
        ).all()
        return [_orm_to_entity(r) for r in rows]

    async def get_allocated_quantity(self, demand_item_id: int) -> float:
        result = await self._db.scalar(
            select(func.sum(BoughtItemAllocationOrmModel.quantity)).where(
                BoughtItemAllocationOrmModel.demand_item_id == demand_item_id
            )
        )
        return result or 0.0

    async def get_allocated_quantity_for_order_item(self, order_item_id: int) -> float:
        return await allocated_quantity_on_order_item(self._db, order_item_id)

    async def get_allocated_quantities_for_order_items(
        self, order_item_ids: list[int]
    ) -> dict[int, float]:
        return await allocated_quantities_on_order_items(self._db, order_item_ids)

    async def save(self, allocation: BoughtItemDemandAllocation) -> BoughtItemDemandAllocation:
        existing = await self._db.scalar(
            select(BoughtItemAllocationOrmModel)
            .where(
                BoughtItemAllocationOrmModel.demand_item_id == allocation.demand_item_id,
                BoughtItemAllocationOrmModel.order_item_id == allocation.order_item_id,
            )
            .limit(1)
        )
        if existing:
            existing.quantity = allocation.quantity
            existing.source = allocation.source.value
            existing.substitute_item_id = allocation.substitute_item_id
            existing.substitute_reason = allocation.substitute_reason
        else:
            existing = BoughtItemAllocationOrmModel(
                demand_item_id=allocation.demand_item_id,
                order_item_id=allocation.order_item_id,
                quantity=allocation.quantity,
                source=allocation.source.value,
                substitute_item_id=allocation.substitute_item_id,
                substitute_reason=allocation.substitute_reason,
                created_by_id=allocation.created_by_id,
            )
            self._db.add(existing)
        await self._db.flush()
        return allocation

    async def delete(self, allocation: BoughtItemDemandAllocation) -> None:
        orm = await self._db.scalar(
            select(BoughtItemAllocationOrmModel)
            .where(
                BoughtItemAllocationOrmModel.demand_item_id == allocation.demand_item_id,
                BoughtItemAllocationOrmModel.order_item_id == allocation.order_item_id,
            )
            .limit(1)
        )
        if orm:
            await self._db.delete(orm)
            await self._db.flush()
