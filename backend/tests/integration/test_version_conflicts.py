"""
The version column of the lifecycle tables on the throwaway SQLite database:
a writer whose session still holds a copy of the row older than the
committed row gets StaleDataError and writes nothing, a writer that re-read
the row under its lock writes, and
the schedule's grouped writes increment the version once per row, record the
row for live sync and leave the loaded row holding what they wrote.
"""

from datetime import UTC
from datetime import datetime
from datetime import timedelta
from typing import Any

import pytest
from sqlalchemy import delete as sa_delete
from sqlalchemy import select
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.exc import StaleDataError

from src.modules.fulfillment.adapters.outbound.persistence.lifecycle_store import (
    sql_lifecycle_repositories,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.bought_item_allocation_model import (
    BoughtItemAllocationOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.bought_item_demand_item_model import (
    BoughtItemDemandItemOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.order_model import OrderOrmModel
from src.modules.fulfillment.adapters.outbound.persistence.models.production_order_file_model import (
    ProductionOrderFileOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.production_order_model import (
    ProductionOrderOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.bought_item_repository.demand_item import (
    SqlAlchemyBoughtItemDemandItemRepository,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.order_repository.order import (
    SqlAlchemyOrderRepository,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.production_lot_repository.lot import (
    SqlAlchemyProductionLotRepository,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.production_order_repository import (
    SqlAlchemyProductionOrderRepository,
)
from src.modules.fulfillment.application.services.lifecycle_reconciler import LifecycleReconciler
from src.modules.fulfillment.domain.errors import LotPositionInUseError
from src.modules.fulfillment.ports.outbound.repositories.production_order_repository import (
    ProductionOrderPlanningFields,
)
from src.modules.platform.adapters.outbound.persistence.session import SessionLocal
from src.modules.platform.domain.exceptions import ConcurrentModificationError
from tests.integration._lot_facts import _SEEDER
from tests.integration.repository_reads._graph import Graph

_START = datetime(2026, 3, 2, 8, 0, tzinfo=UTC)


class _NoBus:
    async def publish(self, event: object) -> None:
        return None


async def _version(session: AsyncSession, model: Any, row_id: int) -> int:
    version = await session.scalar(select(model.version).where(model.id == row_id))
    assert version is not None
    return int(version)


async def test_a_write_from_a_copy_older_than_the_row_is_refused(db: AsyncSession) -> None:
    graph = await Graph.seed(db)
    order_id = (await graph.order()).id

    async with SessionLocal() as first, SessionLocal() as second:
        # The session holds the row it read, as it does while a use case keeps
        # working on it; the identity map would otherwise let it go.
        _held = await first.get_one(OrderOrmModel, order_id)
        mine = await SqlAlchemyOrderRepository(first).get_by_id(order_id)
        theirs = await SqlAlchemyOrderRepository(second).get_by_id(order_id)
        assert mine is not None and theirs is not None
        theirs.note = "theirs"
        await SqlAlchemyOrderRepository(second).save(theirs)
        await second.commit()

        mine.note = "mine"
        with pytest.raises(StaleDataError):
            await SqlAlchemyOrderRepository(first).save(mine)
        await first.rollback()

    async with SessionLocal() as read:
        stored = await SqlAlchemyOrderRepository(read).get_by_id(order_id)
        assert stored is not None
        assert stored.note == "theirs"


async def test_a_write_after_a_locked_read_of_the_row_goes_through(db: AsyncSession) -> None:
    graph = await Graph.seed(db)
    order_id = (await graph.order()).id

    async with SessionLocal() as first, SessionLocal() as second:
        assert await SqlAlchemyOrderRepository(first).get_by_id(order_id) is not None
        theirs = await SqlAlchemyOrderRepository(second).get_by_id(order_id)
        assert theirs is not None
        theirs.note = "theirs"
        await SqlAlchemyOrderRepository(second).save(theirs)
        await second.commit()

        mine = await SqlAlchemyOrderRepository(first).get_by_id_for_update(order_id)
        assert mine is not None
        mine.note = "mine"
        await SqlAlchemyOrderRepository(first).save(mine)
        await first.commit()

    async with SessionLocal() as read:
        stored = await SqlAlchemyOrderRepository(read).get_by_id(order_id)
        assert stored is not None
        assert stored.note == "mine"


async def test_a_production_order_saved_from_a_copy_older_than_the_row_is_refused(
    db: AsyncSession,
) -> None:
    graph = await Graph.seed(db)
    order_id = (await graph.production_order()).id

    async with SessionLocal() as first, SessionLocal() as second:
        mine = await SqlAlchemyProductionOrderRepository(first).get_by_id(order_id)
        theirs = await SqlAlchemyProductionOrderRepository(second).get_by_id(order_id)
        assert mine is not None and theirs is not None
        theirs.note = "theirs"
        await SqlAlchemyProductionOrderRepository(second).save(theirs)
        await second.commit()

        mine.note = "mine"
        with pytest.raises(ConcurrentModificationError):
            await SqlAlchemyProductionOrderRepository(first).save(mine)
        await first.rollback()

    async with SessionLocal() as read:
        stored = await SqlAlchemyProductionOrderRepository(read).get_by_id(order_id)
        assert stored is not None
        assert stored.note == "theirs"


async def test_a_production_order_saved_twice_in_one_transaction_goes_through(
    db: AsyncSession,
) -> None:
    graph = await Graph.seed(db)
    order_id = (await graph.production_order()).id

    async with SessionLocal() as session:
        orders = SqlAlchemyProductionOrderRepository(session)
        order = await orders.get_by_id(order_id)
        assert order is not None
        order.note = "first"
        await orders.save(order)
        order.note = "second"
        await orders.save(order)
        await session.commit()

    async with SessionLocal() as read:
        stored = await SqlAlchemyProductionOrderRepository(read).get_by_id(order_id)
        assert stored is not None
        assert stored.note == "second"


async def test_planning_writes_increment_the_version_once_and_signal_the_row(
    db: AsyncSession,
) -> None:
    graph = await Graph.seed(db)
    order_id = (await graph.production_order()).id

    async with SessionLocal() as session:
        before = await _version(session, ProductionOrderOrmModel, order_id)
        await SqlAlchemyProductionOrderRepository(session).save_planning_fields(
            [
                ProductionOrderPlanningFields(
                    order_id=order_id,
                    planned_start=_START,
                    planned_end=_START + timedelta(hours=2),
                    planned_by_id=None,
                    pinned_when_read=False,
                )
            ]
        )
        held = await session.get_one(ProductionOrderOrmModel, order_id)
        live = dict(session.info.get("live_changes", {}))
        await session.commit()

    assert held.version == before + 1
    assert held.planned_by_id is None
    assert live[("production-orders", order_id)] == "updated"
    async with SessionLocal() as read:
        assert await _version(read, ProductionOrderOrmModel, order_id) == before + 1
        stored = await read.get_one(ProductionOrderOrmModel, order_id)
        assert stored.planned_by_id is None


async def test_a_schedule_write_leaves_the_session_able_to_save_the_row_again(
    db: AsyncSession,
) -> None:
    graph = await Graph.seed(db)
    order_id = (await graph.production_order()).id

    async with SessionLocal() as session:
        orders = SqlAlchemyProductionOrderRepository(session)
        order = await orders.get_by_id(order_id)
        assert order is not None
        order.queue_sequence = 7
        await orders.save_schedule([order])
        again = await orders.get_by_id(order_id)
        assert again is not None
        again.note = "after the schedule write"
        await orders.save(again)
        await session.commit()

    async with SessionLocal() as read:
        stored = await read.get_one(ProductionOrderOrmModel, order_id)
        assert (stored.queue_sequence, stored.note) == (7, "after the schedule write")


async def test_a_planning_write_skips_an_order_that_ended_since_the_walk_read_it(
    db: AsyncSession,
) -> None:
    graph = await Graph.seed(db)
    order_id = (await graph.production_order()).id
    # The order is canceled after the walk read it, and the reconciler
    # cleared its window then.
    await db.execute(
        update(ProductionOrderOrmModel)
        .where(ProductionOrderOrmModel.id == order_id)
        .values(canceled_at=_START, planned_start=None, planned_end=None)
    )
    await db.commit()
    reconciler = LifecycleReconciler(sql_lifecycle_repositories(db), _NoBus())
    reconciler.touch_production_orders([order_id])
    await reconciler.run(_SEEDER, _START, reason="seeded")
    await db.commit()
    assert (await db.get_one(ProductionOrderOrmModel, order_id)).status == "canceled"

    async with SessionLocal() as session:
        await SqlAlchemyProductionOrderRepository(session).save_planning_fields(
            [
                ProductionOrderPlanningFields(
                    order_id=order_id,
                    planned_start=_START,
                    planned_end=_START + timedelta(hours=2),
                    planned_by_id=None,
                    pinned_when_read=False,
                )
            ]
        )
        await session.commit()

    async with SessionLocal() as read:
        stored = await read.get_one(ProductionOrderOrmModel, order_id)
        assert (stored.planned_start, stored.planned_end) == (None, None)


async def test_a_planning_write_skips_an_order_moved_since_the_walk_read_it(
    db: AsyncSession,
) -> None:
    graph = await Graph.seed(db)
    order = await graph.production_order()
    read_place = (order.machine_id, order.machine_pool_id, order.queue_sequence)
    # A reorder moves the order and drops its window after the walk read it.
    await db.execute(
        update(ProductionOrderOrmModel)
        .where(ProductionOrderOrmModel.id == order.id)
        .values(queue_sequence=order.queue_sequence + 5, planned_start=None, planned_end=None)
    )
    await db.commit()

    async with SessionLocal() as session:
        await SqlAlchemyProductionOrderRepository(session).save_planning_fields(
            [
                ProductionOrderPlanningFields(
                    order_id=order.id,
                    planned_start=_START,
                    planned_end=_START + timedelta(hours=2),
                    planned_by_id=None,
                    pinned_when_read=False,
                    place_when_read=read_place,
                )
            ]
        )
        await session.commit()

    async with SessionLocal() as read:
        stored = await read.get_one(ProductionOrderOrmModel, order.id)
        assert (stored.planned_start, stored.planned_end) == (None, None)


async def test_saving_a_demand_removed_meanwhile_is_a_concurrent_modification(
    db: AsyncSession,
) -> None:
    graph = await Graph.seed(db)
    demand = await graph.bought_demand()
    await db.execute(
        sa_delete(BoughtItemAllocationOrmModel).where(
            BoughtItemAllocationOrmModel.demand_item_id == demand.id
        )
    )
    await db.execute(
        sa_delete(BoughtItemDemandItemOrmModel).where(BoughtItemDemandItemOrmModel.id == demand.id)
    )
    await db.commit()

    async with SessionLocal() as session:
        demand.note = "edited from a stale screen"
        with pytest.raises(ConcurrentModificationError):
            await SqlAlchemyBoughtItemDemandItemRepository(session).save(demand)


async def test_a_position_whose_order_holds_files_is_not_deleted(db: AsyncSession) -> None:
    graph = await Graph.seed(db)
    order = await graph.production_order()
    db.add(
        ProductionOrderFileOrmModel(
            production_order_id=order.id,
            file_name="drawing.pdf",
            stored_name="stored-drawing.pdf",
            mime_type="application/pdf",
            size_bytes=1,
            storage_path="production-orders/drawing.pdf",
            sha256="0" * 64,
            category="other",
            created=_START,
            uploaded_by_user_id=graph.uid,
        )
    )
    await db.commit()
    position = await SqlAlchemyProductionLotRepository(db).get_position_by_id(order.lot_position_id)
    assert position is not None

    with pytest.raises(LotPositionInUseError):
        await SqlAlchemyProductionLotRepository(db).delete_position(position)
