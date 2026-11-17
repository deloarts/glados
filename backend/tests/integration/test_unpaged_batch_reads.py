"""
The unpaged reads behind the batch jobs return every matching row, also past
the default page size a paged read stops at: the demands Auto-Assign groups
and the lots of a project whose time budget is apportioned.
"""

import dataclasses
from uuid import uuid4

from src.modules.fulfillment.adapters.outbound.persistence.repositories.made_item_demand_repository import (
    SqlAlchemyMadeItemDemandItemRepository,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.production_lot_repository import (
    SqlAlchemyProductionLotRepository,
)
from src.modules.platform.adapters.outbound.persistence.pagination import DEFAULT_PAGE_SIZE
from tests.integration.repository_reads._graph import Graph

MORE_THAN_A_PAGE = DEFAULT_PAGE_SIZE + 5


async def test_demands_by_status_are_read_past_one_page(db) -> None:
    graph = await Graph.seed(db)
    demand = await graph.made_demand()
    repo = SqlAlchemyMadeItemDemandItemRepository(db)
    for _ in range(MORE_THAN_A_PAGE - 1):
        await repo.save(dataclasses.replace(demand, id=0, public_id=uuid4()))
    await db.commit()

    demands = await repo.get_by_statuses([demand.status])

    assert len(demands) == MORE_THAN_A_PAGE


async def test_the_lots_of_a_project_are_read_past_one_page(db) -> None:
    graph = await Graph.seed(db)
    lot = await graph.lot()
    repo = SqlAlchemyProductionLotRepository(db)
    for n in range(MORE_THAN_A_PAGE - 1):
        await repo.save(
            dataclasses.replace(lot, id=0, public_id=uuid4(), lot_number=f"L-{n + 2}", positions=[])
        )
    await db.commit()

    lots = await repo.get_by_project_id(lot.project_id)

    assert len(lots) == MORE_THAN_A_PAGE
    assert [x.id for x in lots] == sorted(x.id for x in lots)
