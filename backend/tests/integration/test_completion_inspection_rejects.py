"""
An inspection completion with rejected pieces records the accepted count on
the inspection position and then closes the lot short through the shared
disposition. Both steps write the same position row, so they must work on the
same object: saving the lot's own copy of the position, taken before the
completion updated it, would write the stale count back. Runs
the real use case and repositories on the throwaway SQLite file.
"""

import dataclasses

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.bootstrap.adapters.outbound.persistence.repositories.admin_settings_repository import (
    SqlAlchemyAdminSettingsRepository,
)
from src.modules.catalogue.domain.value_objects.step_role import StepRole
from src.modules.fulfillment.adapters.outbound.persistence.lifecycle_store import (
    sql_lifecycle_repositories,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.lot_position_model import (
    LotPositionOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.production_order_completion_model import (
    ProductionOrderCompletionOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.production_order_model import (
    ProductionOrderOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.bought_item_repository.allocation import (
    SqlAlchemyBoughtItemAllocationRepository,
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
from src.modules.fulfillment.adapters.outbound.persistence.repositories.source_item_allocation_repository import (
    SqlAlchemySourceItemAllocationRepository,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.source_item_demand_repository import (
    SqlAlchemySourceItemDemandRepository,
)
from src.modules.fulfillment.application.dto.production_order_dto import (
    RecordProductionOrderCompletionCommand,
)
from src.modules.fulfillment.application.services.lifecycle_reconciler import LifecycleReconciler
from src.modules.fulfillment.application.use_cases.production_order.record_production_order_completion import (
    RecordProductionOrderCompletion,
)
from src.modules.fulfillment.domain.entities.lot_position import LotPosition
from src.modules.fulfillment.domain.entities.lot_step import LotStep
from src.modules.fulfillment.domain.entities.production_order import ProductionOrder
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionKind
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionStatus
from src.modules.fulfillment.domain.value_objects.production_status import ProductionOrderStatus
from src.modules.fulfillment.domain.value_objects.production_status import UrgencyClass
from src.modules.platform.adapters.outbound.persistence.session import SessionLocal
from src.modules.platform.adapters.outbound.persistence.unit_of_work import SqlAlchemyUnitOfWork
from src.modules.platform.domain.value_objects.permission import Permission
from src.shared_kernel.domain.services.clock import now_utc
from tests.integration._lot_facts import give_lot_facts
from tests.integration._production_order_facts import give_production_order_facts
from tests.integration.repository_reads._graph import Graph
from tests.integration.repository_reads._graph import make
from tests.unit.production_lot._helpers import RecordingLotCreation
from tests.unit.production_lot.fakes import FakeMadeItemAllocationRepository
from tests.unit.production_lot.fakes import FakeMadeItemDemandRepository


class _CollectingEventBus:
    def __init__(self) -> None:
        self.published: list[object] = []

    async def publish(self, event: object) -> None:
        self.published.append(event)


async def _seed_inspection_order(db: AsyncSession) -> tuple[Graph, int, int]:
    """A lot of 10 whose first position is done, through a completed order
    of 10, and whose second position is an inspection with one running
    order of 10. Returns the graph, the inspection position id and the
    order id."""
    graph = await Graph.seed(db)
    lot = await graph.lot()
    method = await graph.fabrication_method()
    inspection = await graph.inspection_method()
    lots = SqlAlchemyProductionLotRepository(db)
    first = await lots.save_position(
        make(
            LotPosition,
            sequence=1,
            kind=LotPositionKind.INTERNAL,
            status=LotPositionStatus.COMPLETED,
            quantity=10.0,
            quantity_completed=10.0,
            creator_id=graph.uid,
            lot_id=lot.id,
        )
    )
    await lots.save_step(
        make(
            LotStep,
            sequence=1,
            creator_id=graph.uid,
            fabrication_method_id=method.id,
            lot_id=lot.id,
            position_id=first.id,
            source_process_id=None,
        )
    )
    qa = await lots.save_position(
        make(
            LotPosition,
            sequence=2,
            kind=LotPositionKind.INTERNAL,
            status=LotPositionStatus.IN_PROGRESS,
            quantity=10.0,
            quantity_completed=0.0,
            creator_id=graph.uid,
            lot_id=lot.id,
        )
    )
    await lots.save_step(
        make(
            LotStep,
            sequence=2,
            role=StepRole.INSPECTION,
            inspection_method_id=inspection.id,
            creator_id=graph.uid,
            fabrication_method_id=None,
            lot_id=lot.id,
            position_id=qa.id,
            source_process_id=None,
        )
    )
    orders = SqlAlchemyProductionOrderRepository(db)
    done = await orders.save(
        make(
            ProductionOrder,
            production_order_number="PO-FIRST",
            status=ProductionOrderStatus.COMPLETED,
            priority=UrgencyClass.NORMAL,
            pinned=False,
            queue_sequence=1,
            quantity=10.0,
            quantity_completed=10.0,
            estimated_duration_minutes=30,
            creator_id=graph.uid,
            machine_id=None,
            machine_pool_id=None,
            lot_position_id=first.id,
        )
    )
    await give_production_order_facts(db, done.id)
    order = await orders.save(
        make(
            ProductionOrder,
            production_order_number="PO-QA",
            status=ProductionOrderStatus.IN_PROGRESS,
            priority=UrgencyClass.NORMAL,
            pinned=False,
            queue_sequence=1,
            quantity=10.0,
            quantity_completed=0.0,
            estimated_duration_minutes=30,
            creator_id=graph.uid,
            machine_id=None,
            machine_pool_id=None,
            lot_position_id=qa.id,
        )
    )
    await give_production_order_facts(db, order.id)
    # The graph's lot moves with the positions and orders just added.
    await give_lot_facts(db, lot.id, exact=False)
    await db.commit()
    return graph, qa.id, order.id


async def test_inspection_completion_with_rejects_keeps_the_accepted_count(
    db: AsyncSession,
) -> None:
    graph, position_id, order_id = await _seed_inspection_order(db)
    inspector = dataclasses.replace(
        graph.user,
        permissions=[Permission.WRITE_PRODUCTION_ORDERS, Permission.WRITE_INSPECTIONS],
    )

    follow_up = RecordingLotCreation()
    async with SessionLocal() as session:
        bus = _CollectingEventBus()
        await RecordProductionOrderCompletion(
            SqlAlchemyProductionOrderRepository(session),
            SqlAlchemyProductionLotRepository(session),
            None,
            event_bus=bus,
            uow=SqlAlchemyUnitOfWork(session),
            reconciler=LifecycleReconciler(sql_lifecycle_repositories(session), bus),
            order_item_repo=SqlAlchemyOrderItemRepository(session),
            parent_order_repo=SqlAlchemyOrderRepository(session),
            interruption_repo=SqlAlchemyProductionOrderInterruptionRepository(session),
            source_item_demand_repo=SqlAlchemySourceItemDemandRepository(session),
            source_item_allocation_repo=SqlAlchemySourceItemAllocationRepository(session),
            bought_allocation_repo=SqlAlchemyBoughtItemAllocationRepository(session),
            settings_repo=SqlAlchemyAdminSettingsRepository(session),
            made_item_demand_repo=FakeMadeItemDemandRepository(),
            made_item_allocation_repo=FakeMadeItemAllocationRepository(),
            create_lot=follow_up,
        ).execute(
            inspector,
            order_id,
            RecordProductionOrderCompletionCommand(
                quantity=4.0,
                quantity_accepted=3.0,
                quantity_rejected=1.0,
                quantity_rework=0.0,
                quantity_scrap=1.0,
                completion_date=now_utc().date(),
            ),
        )

    async with SessionLocal() as check:
        position = (
            await check.scalars(
                select(LotPositionOrmModel).where(LotPositionOrmModel.id == position_id)
            )
        ).one()
        order = (
            await check.scalars(
                select(ProductionOrderOrmModel).where(ProductionOrderOrmModel.id == order_id)
            )
        ).one()

    assert order.quantity_completed == 3.0
    assert position.quantity_completed == 3.0
    # Closed short by the scrapped piece, which a replacement lot makes again.
    assert position.quantity == 9.0
    assert [(cmd.quantity, kind) for cmd, kind in follow_up.commands] == [(1.0, "replacement")]  # type: ignore[attr-defined]
    # The reconciler writes the derived count with its changelog line.
    assert any("Completed quantity: 0 → 3 " in line for line in position.changes)


async def test_inspection_completion_keeps_the_reason_of_the_rejects(
    db: AsyncSession,
) -> None:
    graph, _position_id, order_id = await _seed_inspection_order(db)
    inspector = dataclasses.replace(
        graph.user,
        permissions=[Permission.WRITE_PRODUCTION_ORDERS, Permission.WRITE_INSPECTIONS],
    )

    follow_up = RecordingLotCreation()
    async with SessionLocal() as session:
        bus = _CollectingEventBus()
        await RecordProductionOrderCompletion(
            SqlAlchemyProductionOrderRepository(session),
            SqlAlchemyProductionLotRepository(session),
            None,
            event_bus=bus,
            uow=SqlAlchemyUnitOfWork(session),
            reconciler=LifecycleReconciler(sql_lifecycle_repositories(session), bus),
            order_item_repo=SqlAlchemyOrderItemRepository(session),
            parent_order_repo=SqlAlchemyOrderRepository(session),
            interruption_repo=SqlAlchemyProductionOrderInterruptionRepository(session),
            source_item_demand_repo=SqlAlchemySourceItemDemandRepository(session),
            source_item_allocation_repo=SqlAlchemySourceItemAllocationRepository(session),
            bought_allocation_repo=SqlAlchemyBoughtItemAllocationRepository(session),
            settings_repo=SqlAlchemyAdminSettingsRepository(session),
            made_item_demand_repo=FakeMadeItemDemandRepository(),
            made_item_allocation_repo=FakeMadeItemAllocationRepository(),
            create_lot=follow_up,
        ).execute(
            inspector,
            order_id,
            RecordProductionOrderCompletionCommand(
                quantity=4.0,
                quantity_accepted=3.0,
                quantity_rejected=1.0,
                quantity_rework=0.0,
                quantity_scrap=1.0,
                reject_reason="out_of_tolerance",
                completion_date=now_utc().date(),
            ),
        )

    async with SessionLocal() as check:
        completion = (
            await check.scalars(
                select(ProductionOrderCompletionOrmModel).where(
                    ProductionOrderCompletionOrmModel.production_order_id == order_id
                )
            )
        ).one()

    assert completion.reject_reason == "out_of_tolerance"
    assert completion.quantity_rejected == 1.0
