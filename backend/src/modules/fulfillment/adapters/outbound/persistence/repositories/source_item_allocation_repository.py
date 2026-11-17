"""
Concrete SQLAlchemy implementation for the SourceItemDemandAllocation
aggregate. Mirrors bought_item_repository/allocation.py, including
substitution.
"""

from sqlalchemy import func
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.fulfillment.adapters.outbound.persistence.models.source_item_allocation_model import (
    SourceItemAllocationOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories._order_item_allocations import (
    allocated_quantities_on_order_items,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories._order_item_allocations import (
    allocated_quantity_on_order_item,
)
from src.modules.fulfillment.domain.entities.source_item_allocation import (
    SourceItemDemandAllocation,
)
from src.modules.fulfillment.domain.value_objects.source_item_demand_status import (
    SourceItemAllocationSource,
)

# ══════════════════════════════════════════════════════════════════════
# Allocation repository
# ══════════════════════════════════════════════════════════════════════


def _orm_to_entity(r: SourceItemAllocationOrmModel) -> SourceItemDemandAllocation:
    return SourceItemDemandAllocation(
        demand_item_id=r.demand_item_id,
        order_item_id=r.order_item_id,
        quantity=r.quantity,
        source=SourceItemAllocationSource(r.source),
        substitute_source_item_id=r.substitute_source_item_id,
        substitute_reason=r.substitute_reason,
        created_by_id=r.created_by_id,
        created_at=r.created_at,
        changed_at=r.changed_at,
    )


class SqlAlchemySourceItemAllocationRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def get_by_demand_item_id(self, demand_item_id: int) -> list[SourceItemDemandAllocation]:
        rows = (
            await self._db.scalars(
                select(SourceItemAllocationOrmModel).where(
                    SourceItemAllocationOrmModel.demand_item_id == demand_item_id
                )
            )
        ).all()
        return [_orm_to_entity(r) for r in rows]

    async def get_by_demand_item_ids(
        self, demand_item_ids: list[int], *, refresh: bool = False
    ) -> list[SourceItemDemandAllocation]:
        if not demand_item_ids:
            return []
        rows = (
            await self._db.scalars(
                select(SourceItemAllocationOrmModel)
                .where(SourceItemAllocationOrmModel.demand_item_id.in_(demand_item_ids))
                .execution_options(populate_existing=refresh)
            )
        ).all()
        return [_orm_to_entity(r) for r in rows]

    async def get_by_order_item_id(self, order_item_id: int) -> list[SourceItemDemandAllocation]:
        rows = (
            await self._db.scalars(
                select(SourceItemAllocationOrmModel).where(
                    SourceItemAllocationOrmModel.order_item_id == order_item_id
                )
            )
        ).all()
        return [_orm_to_entity(r) for r in rows]

    async def get_by_order_item_ids(
        self, order_item_ids: list[int], *, refresh: bool = False
    ) -> list[SourceItemDemandAllocation]:
        if not order_item_ids:
            return []
        rows = (
            await self._db.scalars(
                select(SourceItemAllocationOrmModel)
                .where(SourceItemAllocationOrmModel.order_item_id.in_(order_item_ids))
                .execution_options(populate_existing=refresh)
            )
        ).all()
        return [_orm_to_entity(r) for r in rows]

    async def get_allocated_quantity(self, demand_item_id: int) -> float:
        result = await self._db.scalar(
            select(func.sum(SourceItemAllocationOrmModel.quantity)).where(
                SourceItemAllocationOrmModel.demand_item_id == demand_item_id
            )
        )
        return result or 0.0

    async def get_allocated_quantity_for_order_item(self, order_item_id: int) -> float:
        return await allocated_quantity_on_order_item(self._db, order_item_id)

    async def get_allocated_quantities_for_order_items(
        self, order_item_ids: list[int]
    ) -> dict[int, float]:
        return await allocated_quantities_on_order_items(self._db, order_item_ids)

    async def _get_orm(
        self, allocation: SourceItemDemandAllocation
    ) -> SourceItemAllocationOrmModel | None:
        row: SourceItemAllocationOrmModel | None = await self._db.scalar(
            select(SourceItemAllocationOrmModel)
            .where(
                SourceItemAllocationOrmModel.demand_item_id == allocation.demand_item_id,
                SourceItemAllocationOrmModel.order_item_id == allocation.order_item_id,
            )
            .limit(1)
        )
        return row

    async def save(self, allocation: SourceItemDemandAllocation) -> SourceItemDemandAllocation:
        existing = await self._get_orm(allocation)
        if existing:
            existing.quantity = allocation.quantity
            existing.source = allocation.source.value
            existing.substitute_source_item_id = allocation.substitute_source_item_id
            existing.substitute_reason = allocation.substitute_reason
        else:
            existing = SourceItemAllocationOrmModel(
                demand_item_id=allocation.demand_item_id,
                order_item_id=allocation.order_item_id,
                quantity=allocation.quantity,
                source=allocation.source.value,
                substitute_source_item_id=allocation.substitute_source_item_id,
                substitute_reason=allocation.substitute_reason,
                created_by_id=allocation.created_by_id,
            )
            self._db.add(existing)
        await self._db.flush()
        return allocation

    async def delete(self, allocation: SourceItemDemandAllocation) -> None:
        orm = await self._get_orm(allocation)
        if orm:
            await self._db.delete(orm)
            await self._db.flush()
