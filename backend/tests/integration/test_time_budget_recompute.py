"""
The project time budget recompute on the SQL repositories: it reads the
project's lots again, so a step edit another session committed after this
session first read the step decides the budget. A step that has its own
estimate per piece takes no share of the project's budget, so once the edit
gave it one, the recompute clears its budget and keeps the estimate.
"""

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.fulfillment.adapters.outbound.persistence.lifecycle_store import (
    sql_lifecycle_repositories,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.lot_step_model import (
    LotStepOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.production_lot_repository.lot import (
    SqlAlchemyProductionLotRepository,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.production_order_repository import (
    SqlAlchemyProductionOrderRepository,
)
from src.modules.fulfillment.application.services.lifecycle_lock_plan import LockPlan
from src.modules.fulfillment.application.services.time_budget_propagation import BudgetOrders
from src.modules.fulfillment.application.services.time_budget_propagation import budget_order_locks
from src.modules.fulfillment.application.services.time_budget_propagation import (
    recompute_project_time_budgets,
)
from src.modules.platform.adapters.outbound.persistence.session import SessionLocal
from src.modules.workspace.adapters.outbound.persistence.models.project_model import ProjectOrmModel
from src.modules.workspace.adapters.outbound.persistence.repositories.project_repository import (
    SqlAlchemyProjectRepository,
)
from tests.integration.repository_reads._graph import Graph


async def test_time_budget_recompute_follows_a_step_edit_committed_meanwhile(
    db: AsyncSession,
) -> None:
    graph = await Graph.seed(db)
    position = await graph.internal_position()
    # Its queued order makes the position internal, which takes a budget.
    await graph.production_order()
    lot = await graph.lot()
    await db.execute(
        update(ProjectOrmModel)
        .where(ProjectOrmModel.id == lot.project_id)
        .values(production_time_budget=600)
    )
    await db.commit()
    [step] = position.steps or (await SqlAlchemyProductionLotRepository(db).get_steps(lot.id))

    async with SessionLocal() as stale, SessionLocal() as other:
        lots = SqlAlchemyProductionLotRepository(stale)
        # This session holds the step as it was, as a request that read the
        # lot before the edit does.
        assert await lots.get_by_project_id(lot.project_id)
        await other.execute(
            update(LotStepOrmModel)
            .where(LotStepOrmModel.id == step.id)
            .values(estimated_minutes_per_piece=7.0)
        )
        await other.commit()

        # The queued order the recompute snapshots again is locked first,
        # as a request locks it with its other lifecycle rows.
        orders = SqlAlchemyProductionOrderRepository(stale)
        lock_plan = LockPlan(sql_lifecycle_repositories(stale))
        await lock_plan.acquire(await budget_order_locks([lot.project_id], lots, orders))
        await recompute_project_time_budgets(
            lot.project_id,
            SqlAlchemyProjectRepository(stale),
            lots,
            BudgetOrders(orders, lock_plan),
        )
        await stale.commit()

    async with SessionLocal() as read:
        stored = await read.get_one(LotStepOrmModel, step.id)
    assert stored.estimated_minutes_per_piece == 7.0
    assert stored.time_budget_per_piece is None
