"""
Every get_by_id_for_update read returns what other transactions committed,
even while its session still holds a copy of the row loaded before the lock,
because the read refreshes that copy. The lot's locked read also refreshes
its positions' production orders and order item fields. Two sessions on the
throwaway SQLite file stand in for two requests; SQLite ignores FOR UPDATE,
so only the refresh is under test here.

The identity map holds rows weakly, so each test keeps a reference to the
rows it loaded first, the way a request that read them before the lock does.
"""

from collections.abc import Awaitable
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import pytest
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.fulfillment.adapters.outbound.persistence.models.bought_item_demand_item_model import (
    BoughtItemDemandItemOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.made_item_demand_item_model import (
    MadeItemDemandItemOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.order_item_model import (
    OrderItemOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.order_model import OrderOrmModel
from src.modules.fulfillment.adapters.outbound.persistence.models.production_lot_model import (
    ProductionLotOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.production_order_model import (
    ProductionOrderOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.source_item_demand_item_model import (
    SourceItemDemandItemOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.bought_item_repository.demand_item import (
    SqlAlchemyBoughtItemDemandItemRepository,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.made_item_demand_repository.demand_item import (
    SqlAlchemyMadeItemDemandItemRepository,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.order_repository.order import (
    SqlAlchemyOrderRepository,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.order_repository.order_item import (
    SqlAlchemyOrderItemRepository,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.production_lot_repository.lot import (
    SqlAlchemyProductionLotRepository,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.production_order_repository import (
    SqlAlchemyProductionOrderRepository,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.source_item_demand_repository import (
    SqlAlchemySourceItemDemandRepository,
)
from src.modules.platform.adapters.outbound.persistence.session import SessionLocal
from tests.integration.repository_reads._graph import Graph


async def _commit_elsewhere(model: Any, row_id: int, **values: Any) -> None:
    """Commits an update through a second session, as another request would."""
    async with SessionLocal() as other:
        await other.execute(update(model).where(model.id == row_id).values(**values))
        await other.commit()


@dataclass(frozen=True)
class _LockRead:
    repository: Callable[[AsyncSession], Any]
    model: Any
    seed: Callable[[Graph], Awaitable[int]]
    column: str
    committed_elsewhere: object


async def _lot(g: Graph) -> int:
    return (await g.lot()).id


async def _order_item(g: Graph) -> int:
    return (await g.bought_order_item()).id


async def _bought_demand(g: Graph) -> int:
    return (await g.bought_demand()).id


async def _made_demand(g: Graph) -> int:
    return (await g.made_demand()).id


async def _source_demand(g: Graph) -> int:
    return (await g.source_demand()).id


async def _production_order(g: Graph) -> int:
    return (await g.production_order()).id


async def _order(g: Graph) -> int:
    return (await g.order()).id


_LOCK_READS = {
    "lot": _LockRead(
        SqlAlchemyProductionLotRepository, ProductionLotOrmModel, _lot, "quantity", 7.0
    ),
    "order_item": _LockRead(
        SqlAlchemyOrderItemRepository, OrderItemOrmModel, _order_item, "quantity", 7.0
    ),
    "bought_demand": _LockRead(
        SqlAlchemyBoughtItemDemandItemRepository,
        BoughtItemDemandItemOrmModel,
        _bought_demand,
        "quantity",
        7.0,
    ),
    "made_demand": _LockRead(
        SqlAlchemyMadeItemDemandItemRepository,
        MadeItemDemandItemOrmModel,
        _made_demand,
        "quantity",
        7.0,
    ),
    "source_demand": _LockRead(
        SqlAlchemySourceItemDemandRepository,
        SourceItemDemandItemOrmModel,
        _source_demand,
        "quantity",
        7.0,
    ),
    "production_order": _LockRead(
        SqlAlchemyProductionOrderRepository,
        ProductionOrderOrmModel,
        _production_order,
        "quantity",
        7.0,
    ),
    "order": _LockRead(
        SqlAlchemyOrderRepository, OrderOrmModel, _order, "note", "changed by another request"
    ),
}


@pytest.mark.parametrize("lock_read", list(_LOCK_READS.values()), ids=list(_LOCK_READS))
async def test_a_lock_read_returns_what_another_request_committed_meanwhile(
    db: AsyncSession, lock_read: _LockRead
) -> None:
    graph = await Graph.seed(db)
    row_id = await lock_read.seed(graph)
    # Not every graph node commits on its own (the source demand does not).
    await db.commit()

    async with SessionLocal() as session:
        held = await session.get(lock_read.model, row_id)
        assert held is not None
        assert getattr(held, lock_read.column) != lock_read.committed_elsewhere

        await _commit_elsewhere(
            lock_read.model, row_id, **{lock_read.column: lock_read.committed_elsewhere}
        )
        locked = await lock_read.repository(session).get_by_id_for_update(row_id)
        assert getattr(held, lock_read.column) == lock_read.committed_elsewhere

    assert locked is not None
    assert getattr(locked, lock_read.column) == lock_read.committed_elsewhere


async def test_the_lot_lock_refreshes_the_orders_and_lines_of_its_positions(
    db: AsyncSession, allow_lifecycle_drift: None
) -> None:
    """The completed count committed elsewhere has no completion row behind
    it, so the position's stored count stays behind its derivation on
    purpose."""
    graph = await Graph.seed(db)
    lot = await graph.lot()
    order = await graph.production_order()
    line = await graph.made_order_item()
    assert line.lot_position_id is not None

    async with SessionLocal() as session:
        held = [
            await session.get(ProductionLotOrmModel, lot.id),
            await session.get(ProductionOrderOrmModel, order.id),
            await session.get(OrderItemOrmModel, line.id),
        ]

        await _commit_elsewhere(ProductionOrderOrmModel, order.id, quantity_completed=4.0)
        # The line's quantity, not a delivered count, which would need its
        # delivery row and status beside it.
        await _commit_elsewhere(OrderItemOrmModel, line.id, quantity=7.0)
        locked = await SqlAlchemyProductionLotRepository(session).get_by_id_for_update(lot.id)
        assert locked is not None
        internal = next(p for p in locked.positions if p.id == order.lot_position_id)
        external = next(p for p in locked.positions if p.id == line.lot_position_id)

        # A plain read after the lock gets the refreshed rows as well.
        siblings = await SqlAlchemyProductionOrderRepository(session).get_by_lot_position_id(
            order.lot_position_id
        )
        assert all(row is not None for row in held)

    assert [o.quantity_completed for o in internal.production_orders] == [4.0]
    assert external.order_item_quantity == 7.0
    assert [o.quantity_completed for o in siblings] == [4.0]
