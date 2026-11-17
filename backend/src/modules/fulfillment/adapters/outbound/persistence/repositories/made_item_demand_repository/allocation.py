"""
Concrete SQLAlchemy implementation for the MadeItemDemandAllocation
aggregate. Mirrors bought_item_repository/allocation.py, keyed by
demand_item_id + lot_id instead of demand_item_id + order_item_id, minus
substitution fields (made items don't support substitution).
"""

from sqlalchemy import func
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.catalogue.domain.value_objects.made_item_status import MadeItemAllocationSource
from src.modules.fulfillment.adapters.outbound.persistence.models.made_item_allocation_model import (
    MadeItemAllocationOrmModel,
)
from src.modules.fulfillment.domain.entities.made_item_allocation import MadeItemDemandAllocation


def _orm_to_entity(orm: MadeItemAllocationOrmModel) -> MadeItemDemandAllocation:
    return MadeItemDemandAllocation(
        demand_item_id=orm.demand_item_id,
        lot_id=orm.lot_id,
        quantity=orm.quantity,
        source=MadeItemAllocationSource(orm.source),
        created_by_id=orm.created_by_id,
        created_at=orm.created_at,
        changed_at=orm.changed_at,
    )


# ══════════════════════════════════════════════════════════════════════
# Allocation repository
# ══════════════════════════════════════════════════════════════════════


class SqlAlchemyMadeItemAllocationRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def get_by_demand_item_id(self, demand_item_id: int) -> list[MadeItemDemandAllocation]:
        rows = (
            await self._db.scalars(
                select(MadeItemAllocationOrmModel).where(
                    MadeItemAllocationOrmModel.demand_item_id == demand_item_id
                )
            )
        ).all()
        return [_orm_to_entity(r) for r in rows]

    async def get_by_demand_item_ids(
        self, demand_item_ids: list[int], *, refresh: bool = False
    ) -> list[MadeItemDemandAllocation]:
        if not demand_item_ids:
            return []
        rows = (
            await self._db.scalars(
                select(MadeItemAllocationOrmModel)
                .where(MadeItemAllocationOrmModel.demand_item_id.in_(demand_item_ids))
                .execution_options(populate_existing=refresh)
            )
        ).all()
        return [_orm_to_entity(r) for r in rows]

    async def get_by_lot_id(self, lot_id: int) -> list[MadeItemDemandAllocation]:
        rows = (
            await self._db.scalars(
                select(MadeItemAllocationOrmModel).where(
                    MadeItemAllocationOrmModel.lot_id == lot_id
                )
            )
        ).all()
        return [_orm_to_entity(r) for r in rows]

    async def get_by_lot_ids(
        self, lot_ids: list[int], *, refresh: bool = False
    ) -> list[MadeItemDemandAllocation]:
        if not lot_ids:
            return []
        rows = (
            await self._db.scalars(
                select(MadeItemAllocationOrmModel)
                .where(MadeItemAllocationOrmModel.lot_id.in_(lot_ids))
                .execution_options(populate_existing=refresh)
            )
        ).all()
        return [_orm_to_entity(r) for r in rows]

    async def get_allocated_quantity(self, demand_item_id: int) -> float:
        result = await self._db.scalar(
            select(func.sum(MadeItemAllocationOrmModel.quantity)).where(
                MadeItemAllocationOrmModel.demand_item_id == demand_item_id
            )
        )
        return result or 0.0

    async def save(self, allocation: MadeItemDemandAllocation) -> MadeItemDemandAllocation:
        existing = await self._db.scalar(
            select(MadeItemAllocationOrmModel)
            .where(
                MadeItemAllocationOrmModel.demand_item_id == allocation.demand_item_id,
                MadeItemAllocationOrmModel.lot_id == allocation.lot_id,
            )
            .limit(1)
        )
        if existing:
            existing.quantity = allocation.quantity
            existing.source = allocation.source.value
        else:
            existing = MadeItemAllocationOrmModel(
                demand_item_id=allocation.demand_item_id,
                lot_id=allocation.lot_id,
                quantity=allocation.quantity,
                source=allocation.source.value,
                created_by_id=allocation.created_by_id,
            )
            self._db.add(existing)
        await self._db.flush()
        return allocation

    async def delete(self, allocation: MadeItemDemandAllocation) -> None:
        orm = await self._db.scalar(
            select(MadeItemAllocationOrmModel)
            .where(
                MadeItemAllocationOrmModel.demand_item_id == allocation.demand_item_id,
                MadeItemAllocationOrmModel.lot_id == allocation.lot_id,
            )
            .limit(1)
        )
        if orm:
            await self._db.delete(orm)
            await self._db.flush()
