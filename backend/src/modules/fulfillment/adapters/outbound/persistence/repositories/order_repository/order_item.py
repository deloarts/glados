"""
Concrete SQLAlchemy implementation for the OrderItem aggregate.
"""

from sqlalchemy import asc
from sqlalchemy import func
from sqlalchemy import or_
from sqlalchemy import select
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy.orm.interfaces import ORMOption

from src.modules.fulfillment.adapters.outbound.persistence.models.order_extra_cost_model import (
    OrderExtraCostOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.order_item_model import (
    OrderItemOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories._lifecycle_rows import (
    lock_rows,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.order_repository._mappers import (
    order_item_entity_to_dict,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.order_repository._mappers import (
    order_item_load_options,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.order_repository._mappers import (
    order_item_orm_to_entity,
)
from src.modules.fulfillment.domain.entities.order_item import OrderItem
from src.modules.fulfillment.domain.value_objects.order_status import OrderItemStatus
from src.modules.fulfillment.domain.value_objects.order_status import OrderLineType
from src.modules.platform.adapters.outbound.persistence.statements import by_id
from src.modules.platform.domain.exceptions import ConcurrentModificationError


def _delete_load_options() -> tuple[ORMOption, ...]:
    """The child collections the unit of work dereferences when an order
    item is deleted, loaded with the row so the delete issues no lazy load."""
    return (
        selectinload(OrderItemOrmModel.delivery_records),
        selectinload(OrderItemOrmModel.allocations),
        selectinload(OrderItemOrmModel.source_item_allocations),
    )


# ══════════════════════════════════════════════════════════════════════
# OrderItem repository
# ══════════════════════════════════════════════════════════════════════


class SqlAlchemyOrderItemRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def _reload(self, id: int) -> OrderItemOrmModel:
        """Re-selects a just-written row with everything the mapper reads.
        populate_existing re-reads every column, so server defaults arrive as
        with refresh(), and applies the loader options to the object already
        in the identity map."""
        return (
            await self._db.scalars(
                by_id(OrderItemOrmModel, id, *order_item_load_options(), refresh=True)
            )
        ).one()

    async def get_by_id(self, id: int) -> OrderItem | None:
        orm = await self._db.scalar(
            by_id(OrderItemOrmModel, id, *order_item_load_options()).limit(1)
        )
        return order_item_orm_to_entity(orm) if orm else None

    async def get_by_id_for_update(self, id: int) -> OrderItem | None:
        orm = await self._db.scalar(
            by_id(
                OrderItemOrmModel, id, *order_item_load_options(), for_update=True, refresh=True
            ).limit(1)
        )
        return order_item_orm_to_entity(orm) if orm else None

    async def get_by_ids(self, ids: list[int], *, refresh: bool = False) -> list[OrderItem]:
        if not ids:
            return []
        rows = (
            await self._db.scalars(
                select(OrderItemOrmModel)
                .options(*order_item_load_options())
                .where(OrderItemOrmModel.id.in_(ids))
                .execution_options(populate_existing=refresh)
            )
        ).all()
        return [order_item_orm_to_entity(r) for r in rows]

    async def lock_for_update(self, ids: list[int]) -> None:
        await lock_rows(self._db, OrderItemOrmModel, OrderItemOrmModel.id, ids)

    async def get_settled_short(self, limit: int) -> list[OrderItem]:
        rows = (
            await self._db.scalars(
                select(OrderItemOrmModel)
                .options(*order_item_load_options())
                .where(
                    OrderItemOrmModel.canceled_at.is_(None),
                    OrderItemOrmModel.line_type.in_(
                        (OrderLineType.BOUGHT.value, OrderLineType.SOURCE.value)
                    ),
                    or_(
                        OrderItemOrmModel.quantity_rejected_lost > 0,
                        OrderItemOrmModel.closed_short_at.is_not(None),
                    ),
                )
                .order_by(OrderItemOrmModel.changed.desc(), OrderItemOrmModel.id.desc())
                .limit(limit)
            )
        ).all()
        return [order_item_orm_to_entity(r) for r in rows]

    async def get_by_order_id(self, order_id: int) -> list[OrderItem]:
        rows = (
            await self._db.scalars(
                select(OrderItemOrmModel)
                .options(*order_item_load_options())
                .where(OrderItemOrmModel.order_id == order_id)
                .order_by(asc(OrderItemOrmModel.position))
            )
        ).all()
        return [order_item_orm_to_entity(r) for r in rows]

    async def get_by_order_ids(
        self, order_ids: list[int], *, refresh: bool = False
    ) -> list[OrderItem]:
        if not order_ids:
            return []
        rows = (
            await self._db.scalars(
                select(OrderItemOrmModel)
                .options(*order_item_load_options())
                .where(OrderItemOrmModel.order_id.in_(order_ids))
                .order_by(
                    asc(OrderItemOrmModel.order_id),
                    asc(OrderItemOrmModel.position),
                )
                .execution_options(populate_existing=refresh)
            )
        ).all()
        return [order_item_orm_to_entity(r) for r in rows]

    async def next_position(self, order_id: int) -> int:
        result = await self._db.scalar(
            select(func.max(OrderItemOrmModel.position)).where(
                OrderItemOrmModel.order_id == order_id
            )
        )
        return (result or 0) + 1

    async def get_by_bought_item_id(self, bought_item_id: int) -> list[OrderItem]:
        """Used by AutoAllocate to find eligible order items."""
        eligible = {
            OrderItemStatus.ORDERED.value,
            OrderItemStatus.PARTIALLY_DELIVERED.value,
        }
        rows = (
            await self._db.scalars(
                select(OrderItemOrmModel)
                .options(*order_item_load_options())
                .where(
                    OrderItemOrmModel.bought_item_id == bought_item_id,
                    OrderItemOrmModel.status.in_(eligible),
                )
            )
        ).all()
        return [order_item_orm_to_entity(r) for r in rows]

    async def get_by_lot_position_id(self, lot_position_id: int) -> OrderItem | None:
        """The position's line: its newest live line, else the newest of the
        canceled lines beside it, None without any. A position holds at most
        one open line; earlier live lines were closed short."""
        orm = await self._db.scalar(
            select(OrderItemOrmModel)
            .options(*order_item_load_options())
            .where(OrderItemOrmModel.lot_position_id == lot_position_id)
            .order_by(OrderItemOrmModel.canceled_at.is_not(None), OrderItemOrmModel.id.desc())
            .limit(1)
        )
        return order_item_orm_to_entity(orm) if orm else None

    async def get_by_lot_position_ids(
        self, lot_position_ids: list[int], *, refresh: bool = False
    ) -> list[OrderItem]:
        """Batch counterpart to get_by_lot_position_id, one query for many
        positions instead of one query per position, mirroring
        SqlAlchemyProductionOrderRepository.get_by_lot_position_ids, used
        by the scheduler's chain-walk prefetch
        (_context._prefetch_order_items_by_position)."""
        if not lot_position_ids:
            return []
        rows = (
            await self._db.scalars(
                select(OrderItemOrmModel)
                .options(*order_item_load_options())
                .where(OrderItemOrmModel.lot_position_id.in_(lot_position_ids))
                .execution_options(populate_existing=refresh)
            )
        ).all()
        return [order_item_orm_to_entity(r) for r in rows]

    async def get_by_source_item_id(self, source_item_id: int) -> list[OrderItem]:
        """Used by AutoAllocateSourceItemDemand to find eligible order items."""
        eligible = {
            OrderItemStatus.ORDERED.value,
            OrderItemStatus.PARTIALLY_DELIVERED.value,
        }
        rows = (
            await self._db.scalars(
                select(OrderItemOrmModel)
                .options(*order_item_load_options())
                .where(
                    OrderItemOrmModel.source_item_id == source_item_id,
                    OrderItemOrmModel.status.in_(eligible),
                )
            )
        ).all()
        return [order_item_orm_to_entity(r) for r in rows]

    async def save(self, item: OrderItem) -> OrderItem:
        if item.id == 0:
            orm = OrderItemOrmModel(**order_item_entity_to_dict(item))
            self._db.add(orm)
            await self._db.flush()
            return order_item_orm_to_entity(await self._reload(orm.id))
        existing = await self._db.get(OrderItemOrmModel, item.id)
        if not existing:
            raise ConcurrentModificationError(
                f"OrderItemOrmModel id={item.id} was removed"
                " while this request worked on it; reload and try again."
            )
        orm = existing
        for k, v in order_item_entity_to_dict(item).items():
            setattr(orm, k, v)
        await self._db.flush()
        return order_item_orm_to_entity(await self._reload(orm.id))

    async def delete(self, item: OrderItem) -> None:
        orm = await self._db.scalar(
            select(OrderItemOrmModel)
            .where(OrderItemOrmModel.id == item.id)
            .options(*_delete_load_options())
        )
        if orm:
            # An extra cost that named the line now belongs to the whole
            # order. The foreign key does the same on Postgres; SQLite runs
            # without foreign key enforcement, so it is written here.
            await self._db.execute(
                update(OrderExtraCostOrmModel)
                .where(OrderExtraCostOrmModel.order_item_id == item.id)
                .values(order_item_id=None)
            )
            await self._db.delete(orm)
            await self._db.flush()
