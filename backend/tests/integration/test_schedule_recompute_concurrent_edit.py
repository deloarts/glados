"""
The global schedule recompute reads every order, walks for a while, and then
writes. A change another request commits in between survives: the recompute
writes only the planned window and its author, and skips an order whose pin
or queue place changed since its read. Runs the real recompute and repositories on the
throwaway SQLite file, with a second session committing right after the
walk's read.
"""

from datetime import UTC
from datetime import datetime
from typing import Any

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from src.bootstrap.adapters.outbound.persistence.repositories.admin_settings_repository import (
    SqlAlchemyAdminSettingsRepository,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.production_order_model import (
    ProductionOrderOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.machine_calendar_repository import (
    SqlAlchemyMachineCalendarRepository,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.machine_downtime_repository import (
    SqlAlchemyMachineDowntimeRepository,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.machine_pool_repository import (
    SqlAlchemyMachinePoolRepository,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.made_item_demand_repository.allocation import (
    SqlAlchemyMadeItemAllocationRepository,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.made_item_demand_repository.demand_item import (
    SqlAlchemyMadeItemDemandItemRepository,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.order_repository.order_item import (
    SqlAlchemyOrderItemRepository,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.production_lot_repository.lot import (
    SqlAlchemyProductionLotRepository,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.production_machine_repository import (
    SqlAlchemyProductionMachineRepository,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.production_order_repository import (
    SqlAlchemyProductionOrderRepository,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.source_item_allocation_repository import (
    SqlAlchemySourceItemAllocationRepository,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.source_item_demand_repository import (
    SqlAlchemySourceItemDemandRepository,
)
from src.modules.fulfillment.application.services.scheduling_context import SchedulingRepos
from src.modules.fulfillment.application.use_cases.production_schedule.recompute_machine_schedule import (
    RecomputeMachineSchedule,
)
from src.modules.fulfillment.domain.entities.admin_settings.production import (
    AdminProductionSettings,
)
from src.modules.fulfillment.domain.entities.production_machine import ProductionMachine
from src.modules.fulfillment.domain.entities.production_order import ProductionOrder
from src.modules.platform.adapters.outbound.persistence.session import SessionLocal
from src.modules.platform.adapters.outbound.persistence.unit_of_work import SqlAlchemyUnitOfWork
from tests.integration.repository_reads._graph import Graph
from tests.integration.repository_reads._graph import make

_PINNED_START = datetime(2026, 2, 2, 8, 0, tzinfo=UTC)
_PINNED_END = datetime(2026, 2, 2, 9, 0, tzinfo=UTC)


async def _commit_elsewhere(order_id: int, **values: Any) -> None:
    """Commits an update through a second session, as another request would."""
    async with SessionLocal() as other:
        await other.execute(
            update(ProductionOrderOrmModel)
            .where(ProductionOrderOrmModel.id == order_id)
            .values(**values)
        )
        await other.commit()


class _CommitsDuringTheWalk(SqlAlchemyProductionOrderRepository):
    """Commits `values` onto one order right after the walk has read it."""

    def __init__(self, db: AsyncSession, order_id: int, **values: Any) -> None:
        super().__init__(db)
        self._order_id = order_id
        self._values = values

    async def get_all_non_terminal(self) -> list[ProductionOrder]:
        orders = await super().get_all_non_terminal()
        await _commit_elsewhere(self._order_id, **self._values)
        return orders


def _recompute(
    session: AsyncSession, orders: SqlAlchemyProductionOrderRepository
) -> RecomputeMachineSchedule:
    return RecomputeMachineSchedule(
        repos=SchedulingRepos(
            orders=orders,
            lots=SqlAlchemyProductionLotRepository(session),
            order_items=SqlAlchemyOrderItemRepository(session),
            source_item_demands=SqlAlchemySourceItemDemandRepository(session),
            source_item_allocations=SqlAlchemySourceItemAllocationRepository(session),
            made_item_allocations=SqlAlchemyMadeItemAllocationRepository(session),
            made_item_demands=SqlAlchemyMadeItemDemandItemRepository(session),
            settings=SqlAlchemyAdminSettingsRepository(session),
        ),
        machine_repo=SqlAlchemyProductionMachineRepository(session),
        calendar_repo=SqlAlchemyMachineCalendarRepository(session),
        settings_repo=SqlAlchemyAdminSettingsRepository(session),
        pool_repo=SqlAlchemyMachinePoolRepository(session),
        downtime_repo=SqlAlchemyMachineDowntimeRepository(session),
        uow=SqlAlchemyUnitOfWork(session),
    )


async def _seed(db: AsyncSession) -> tuple[Graph, ProductionOrder, ProductionMachine]:
    """A running, unpinned order on one machine, which the walk anchors at its
    start and therefore dates, and a second machine to move it to."""
    await SqlAlchemyAdminSettingsRepository(db).save_production(
        AdminProductionSettings(
            id=1,
            production_order_number_format="PON-{seq:05d}",
            default_weekly_hours={0: 480, 1: 480, 2: 480, 3: 480, 4: 480, 5: 0, 6: 0},
            default_external_lead_days=0,
            response_time_days=0,
            require_qa=False,
        )
    )
    graph = await Graph.seed(db)
    order = await graph.production_order()
    method = await graph.fabrication_method()
    other_machine = await SqlAlchemyProductionMachineRepository(db).save(
        make(
            ProductionMachine,
            internal_name="MILL-2",
            fabrication_method_ids=[method.id],
            creator_id=graph.uid,
        )
    )
    await db.commit()
    return graph, order, other_machine


async def _read_back(order_id: int) -> ProductionOrderOrmModel:
    async with SessionLocal() as check:
        row = await check.get(ProductionOrderOrmModel, order_id)
        assert row is not None
        return row


async def test_a_machine_change_committed_during_the_walk_survives(db: AsyncSession) -> None:
    graph, order, other_machine = await _seed(db)
    assert order.planned_by_id == graph.uid

    async with SessionLocal() as session:
        orders = _CommitsDuringTheWalk(
            session, order.id, machine_id=other_machine.id, machine_pool_id=None, queue_sequence=3
        )
        await _recompute(session, orders).execute_all()

    row = await _read_back(order.id)
    assert (row.machine_id, row.machine_pool_id, row.queue_sequence) == (other_machine.id, None, 3)
    # The window the walk computed belongs to the old queue place, so it is
    # not written; the walk the move requested places the order again.
    assert row.planned_by_id == graph.uid


async def test_a_window_pinned_during_the_walk_is_kept(db: AsyncSession) -> None:
    graph, order, _ = await _seed(db)

    async with SessionLocal() as session:
        orders = _CommitsDuringTheWalk(
            session,
            order.id,
            pinned=True,
            planned_start=_PINNED_START,
            planned_end=_PINNED_END,
            planned_by_id=graph.other_user.id,
        )
        await _recompute(session, orders).execute_all()

    row = await _read_back(order.id)
    assert row.pinned is True
    assert row.planned_by_id == graph.other_user.id
    assert row.planned_start is not None and row.planned_end is not None
    assert row.planned_start.replace(tzinfo=UTC) == _PINNED_START
    assert row.planned_end.replace(tzinfo=UTC) == _PINNED_END


async def test_the_walk_reads_what_was_committed_after_its_session_loaded_the_order(
    db: AsyncSession,
) -> None:
    _, order, other_machine = await _seed(db)

    async with SessionLocal() as session:
        held = await session.get(ProductionOrderOrmModel, order.id)
        assert held is not None
        await _commit_elsewhere(order.id, machine_id=other_machine.id)

        walked = await SqlAlchemyProductionOrderRepository(session).get_all_non_terminal()

    assert [o.machine_id for o in walked if o.id == order.id] == [other_machine.id]
