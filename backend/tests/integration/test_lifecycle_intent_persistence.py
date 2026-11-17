"""
Every lifecycle intent and the interruption reason survive a save and a
fresh read through the real repositories on the throwaway SQLite database,
and each save increments the row's version exactly once. The rows are
seeded through the repository read graph and read back on a separate
session, so a read sees what was committed rather than the seeding
session's identity map.
"""

from datetime import UTC
from datetime import datetime
from typing import Any

from sqlalchemy import select
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
    SqlAlchemyProductionOrderInterruptionRepository,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.production_order_repository import (
    SqlAlchemyProductionOrderRepository,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.source_item_demand_repository import (
    SqlAlchemySourceItemDemandRepository,
)
from src.modules.fulfillment.domain.entities.production_order_interruption import (
    ProductionOrderInterruption,
)
from src.modules.fulfillment.domain.value_objects.interruption_reason import InterruptionReason
from src.modules.fulfillment.domain.value_objects.lot_status import LotStatus
from src.modules.fulfillment.domain.value_objects.order_status import OrderItemStatus
from src.modules.fulfillment.domain.value_objects.order_status import OrderStatus
from src.modules.platform.adapters.outbound.persistence.session import SessionLocal
from tests.integration.repository_reads._graph import Graph

FIRST = datetime(2026, 9, 2, 9, 30, tzinfo=UTC)
SECOND = datetime(2026, 9, 3, 10, 45, tzinfo=UTC)
THIRD = datetime(2026, 9, 4, 11, 15, tzinfo=UTC)


def utc(value: datetime | None) -> datetime | None:
    """SQLite returns timestamps without their zone, all of them UTC."""
    if value is None or value.tzinfo is not None:
        return value
    return value.replace(tzinfo=UTC)


async def _version(session: AsyncSession, model: Any, row_id: int) -> int:
    version = await session.scalar(select(model.version).where(model.id == row_id))
    assert version is not None
    return int(version)


async def test_lot_intents_round_trip(db: AsyncSession) -> None:
    graph = await Graph.seed(db)
    lot = await graph.lot()
    # With the status the intents give, so the row stays consistent.
    lot.held_at, lot.canceled_at, lot.force_completed_at = FIRST, SECOND, THIRD
    lot.status = LotStatus.CANCELED
    lot_version = await _version(db, ProductionLotOrmModel, lot.id)
    await SqlAlchemyProductionLotRepository(db).save(lot)
    await db.commit()

    async with SessionLocal() as read:
        loaded = await SqlAlchemyProductionLotRepository(read).get_by_id(lot.id)
        assert loaded is not None
        assert (utc(loaded.held_at), utc(loaded.canceled_at), utc(loaded.force_completed_at)) == (
            FIRST,
            SECOND,
            THIRD,
        )
        assert await _version(read, ProductionLotOrmModel, lot.id) == lot_version + 1


async def test_order_and_line_intents_round_trip(db: AsyncSession) -> None:
    graph = await Graph.seed(db)
    order = await graph.order()
    line = await graph.bought_order_item()
    # With the status the intents give, so the rows stay consistent.
    order_version = await _version(db, OrderOrmModel, order.id)
    line_version = await _version(db, OrderItemOrmModel, line.id)
    order.requested_at, order.canceled_at, order.status = FIRST, SECOND, OrderStatus.CANCELED
    await SqlAlchemyOrderRepository(db).save(order)
    line.requested_at, line.canceled_at, line.status = SECOND, THIRD, OrderItemStatus.CANCELED
    await SqlAlchemyOrderItemRepository(db).save(line)
    await db.commit()

    async with SessionLocal() as read:
        loaded_order = await SqlAlchemyOrderRepository(read).get_by_id(order.id)
        loaded_line = await SqlAlchemyOrderItemRepository(read).get_by_id(line.id)
        assert loaded_order is not None and loaded_line is not None
        assert (utc(loaded_order.requested_at), utc(loaded_order.canceled_at)) == (FIRST, SECOND)
        assert (utc(loaded_line.requested_at), utc(loaded_line.canceled_at)) == (SECOND, THIRD)
        assert await _version(read, OrderOrmModel, order.id) == order_version + 1
        assert await _version(read, OrderItemOrmModel, line.id) == line_version + 1


async def test_bought_and_made_demand_intents_round_trip(
    db: AsyncSession, allow_lifecycle_drift: None
) -> None:
    # The stored status is left as seeded under its new intents, which only a
    # use case would reconcile.
    graph = await Graph.seed(db)
    bought = await graph.bought_demand()
    made = await graph.made_demand()
    bought_version = await _version(db, BoughtItemDemandItemOrmModel, bought.id)
    made_version = await _version(db, MadeItemDemandItemOrmModel, made.id)
    bought.canceled_at = FIRST
    await SqlAlchemyBoughtItemDemandItemRepository(db).save(bought)
    made.fulfilled_manually_at = SECOND
    await SqlAlchemyMadeItemDemandItemRepository(db).save(made)
    await db.commit()

    async with SessionLocal() as read:
        loaded_bought = await SqlAlchemyBoughtItemDemandItemRepository(read).get_by_id(bought.id)
        loaded_made = await SqlAlchemyMadeItemDemandItemRepository(read).get_by_id(made.id)
        assert loaded_bought is not None and loaded_made is not None
        assert (utc(loaded_bought.canceled_at), loaded_bought.fulfilled_manually_at) == (
            FIRST,
            None,
        )
        assert (loaded_made.canceled_at, utc(loaded_made.fulfilled_manually_at)) == (None, SECOND)
        assert await _version(read, BoughtItemDemandItemOrmModel, bought.id) == bought_version + 1
        assert await _version(read, MadeItemDemandItemOrmModel, made.id) == made_version + 1


async def test_source_demand_intents_round_trip(
    db: AsyncSession, allow_lifecycle_drift: None
) -> None:
    # The stored status is left as seeded under its new intents, which only a
    # use case would reconcile.
    graph = await Graph.seed(db)
    demand = await graph.source_demand()
    demand_version = await _version(db, SourceItemDemandItemOrmModel, demand.id)
    demand.canceled_at, demand.fulfilled_manually_at = FIRST, SECOND
    await SqlAlchemySourceItemDemandRepository(db).save(demand)
    await db.commit()

    async with SessionLocal() as read:
        loaded = await SqlAlchemySourceItemDemandRepository(read).get_by_id(demand.id)
        assert loaded is not None
        assert (utc(loaded.canceled_at), utc(loaded.fulfilled_manually_at)) == (FIRST, SECOND)
        assert await _version(read, SourceItemDemandItemOrmModel, demand.id) == demand_version + 1


async def test_production_order_intent_and_interruption_reason_round_trip(
    db: AsyncSession, allow_lifecycle_drift: None
) -> None:
    # The stored status is left as seeded under its new intents, which only a
    # use case would reconcile.
    graph = await Graph.seed(db)
    order = await graph.production_order()
    order_version = await _version(db, ProductionOrderOrmModel, order.id)
    order.canceled_at = THIRD
    await SqlAlchemyProductionOrderRepository(db).save(order)
    default_row = await graph.interruption()
    hold_row = await SqlAlchemyProductionOrderInterruptionRepository(db).add(
        ProductionOrderInterruption(
            id=0,
            production_order_id=order.id,
            paused_at=FIRST,
            resumed_at=None,
            paused_by_id=graph.uid,
            resumed_by_id=None,
            created=FIRST,
            reason=InterruptionReason.LOT_HOLD,
        )
    )
    await db.commit()

    async with SessionLocal() as read:
        loaded = await SqlAlchemyProductionOrderRepository(read).get_by_id(order.id)
        assert loaded is not None
        assert utc(loaded.canceled_at) == THIRD
        assert await _version(read, ProductionOrderOrmModel, order.id) == order_version + 1
        reasons = {
            row.id: row.reason
            for row in await SqlAlchemyProductionOrderInterruptionRepository(read).get_by_order_ids(
                [order.id]
            )
        }
        assert reasons == {
            default_row.id: InterruptionReason.MANUAL.value,
            hold_row.id: InterruptionReason.LOT_HOLD.value,
        }
        assert {i.id: i.reason for i in loaded.interruptions} == reasons
