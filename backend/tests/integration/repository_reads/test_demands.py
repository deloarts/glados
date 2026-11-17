"""
Read scenarios for made, bought and source item demands, their
allocations and buckets. See the package docstring for how the scenarios
work.
"""

from datetime import timedelta
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.fulfillment.adapters.outbound.persistence.repositories.bought_item_demand_bucket_repository import (
    SqlAlchemyBoughtItemDemandBucketRepository,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.bought_item_repository.allocation import (
    SqlAlchemyBoughtItemAllocationRepository,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.bought_item_repository.demand_item import (
    SqlAlchemyBoughtItemDemandItemRepository,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.made_item_demand_bucket_repository import (
    SqlAlchemyMadeItemDemandBucketRepository,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.made_item_demand_repository.allocation import (
    SqlAlchemyMadeItemAllocationRepository,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.made_item_demand_repository.demand_item import (
    SqlAlchemyMadeItemDemandItemRepository,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.source_item_allocation_repository import (
    SqlAlchemySourceItemAllocationRepository,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.source_item_demand_bucket_repository import (
    SqlAlchemySourceItemDemandBucketRepository,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.source_item_demand_repository import (
    SqlAlchemySourceItemDemandRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.bought_item_demand_bucket_repository import (
    BoughtItemDemandBucketFilterDto,
)
from src.modules.fulfillment.ports.outbound.repositories.bought_item_demand_repository import (
    DemandItemFilterDto,
)
from src.modules.fulfillment.ports.outbound.repositories.made_item_demand_bucket_repository import (
    MadeItemDemandBucketFilterDto,
)
from src.modules.fulfillment.ports.outbound.repositories.made_item_demand_repository import (
    MadeItemDemandFilterDto,
)
from src.modules.fulfillment.ports.outbound.repositories.source_item_demand_bucket_repository import (
    SourceItemDemandBucketFilterDto,
)
from src.modules.fulfillment.ports.outbound.repositories.source_item_demand_repository import (
    SourceItemDemandFilterDto,
)
from tests.integration.repository_reads._graph import TODAY
from tests.integration.repository_reads._graph import Graph
from tests.integration.repository_reads._harness import Scenarios

SCENARIOS = Scenarios()


@SCENARIOS.register(SqlAlchemyMadeItemDemandItemRepository)
async def _made_demands(g: Graph, r: Any) -> None:
    await g.full_lot()
    demand = await g.made_demand()
    await r.get_by_id(demand.id)
    await r.get_by_id_for_update(demand.id)
    await r.get_by_ids([demand.id])
    await r.get_ids_after(0, 10)
    await r.get_by_project_id(demand.project_id)
    await r.get_by_statuses([demand.status])
    await r.get_multi(MadeItemDemandFilterDto())
    await r.maybe_empty.get_multi(MadeItemDemandFilterDto(todo_horizon=TODAY))
    await r.count_by_status()
    await r.get_pipeline(TODAY - timedelta(days=30))


@SCENARIOS.register(SqlAlchemyMadeItemAllocationRepository)
async def _made_allocations(g: Graph, r: Any) -> None:
    allocation = await g.made_allocation()
    assert allocation.lot_id is not None
    await r.get_allocated_quantity(allocation.demand_item_id)
    await r.get_by_demand_item_id(allocation.demand_item_id)
    await r.get_by_demand_item_ids([allocation.demand_item_id])
    await r.get_by_lot_id(allocation.lot_id)
    await r.get_by_lot_ids([allocation.lot_id])


@SCENARIOS.register(SqlAlchemyBoughtItemDemandItemRepository)
async def _bought_demands(g: Graph, r: Any) -> None:
    await g.bought_allocation()
    demand = await g.bought_demand()
    await r.get_by_id(demand.id)
    await r.get_by_id_for_update(demand.id)
    await r.get_by_ids([demand.id])
    await r.get_ids_after(0, 10)
    await r.get_by_project_id(demand.project_id)
    await r.get_multi(DemandItemFilterDto())
    await r.maybe_empty.get_multi(DemandItemFilterDto(todo_horizon=TODAY))
    await r.count_by_status()
    await r.get_pipeline(TODAY - timedelta(days=30))


@SCENARIOS.register(SqlAlchemyBoughtItemAllocationRepository)
async def _bought_allocations(g: Graph, r: Any) -> None:
    allocation = await g.bought_allocation()
    assert allocation.order_item_id is not None
    await r.get_allocated_quantity(allocation.demand_item_id)
    await r.get_allocated_quantity_for_order_item(allocation.order_item_id)
    await r.get_allocated_quantities_for_order_items([allocation.order_item_id])
    await r.get_by_demand_item_id(allocation.demand_item_id)
    await r.get_by_demand_item_ids([allocation.demand_item_id])
    await r.get_by_order_item_id(allocation.order_item_id)
    await r.get_by_order_item_ids([allocation.order_item_id])


@SCENARIOS.register(SqlAlchemySourceItemDemandRepository)
async def _source_demands(g: Graph, r: Any) -> None:
    await g.full_lot()
    demand = await g.source_demand()
    await r.get_by_id(demand.id)
    await r.get_by_id_for_update(demand.id)
    await r.get_by_ids([demand.id])
    await r.get_ids_after(0, 10)
    await r.get_multi(SourceItemDemandFilterDto())
    await r.maybe_empty.get_multi(SourceItemDemandFilterDto(todo_horizon=TODAY))
    await r.count_by_status()


@SCENARIOS.register(SqlAlchemySourceItemAllocationRepository)
async def _source_allocations(g: Graph, r: Any) -> None:
    allocation = await g.source_allocation()
    assert allocation.order_item_id is not None
    await r.get_allocated_quantity(allocation.demand_item_id)
    await r.get_allocated_quantity_for_order_item(allocation.order_item_id)
    await r.get_allocated_quantities_for_order_items([allocation.order_item_id])
    await r.get_by_demand_item_id(allocation.demand_item_id)
    await r.get_by_demand_item_ids([allocation.demand_item_id])
    await r.get_by_order_item_id(allocation.order_item_id)
    await r.get_by_order_item_ids([allocation.order_item_id])


async def _buckets(r: Any, bucket: Any, filters: object) -> None:
    await r.get_by_id(bucket.id)
    await r.get_by_name(bucket.name)
    await r.get_multi(filters)


@SCENARIOS.register(SqlAlchemyMadeItemDemandBucketRepository)
async def _made_buckets(g: Graph, r: Any) -> None:
    await _buckets(r, await g.made_bucket(), MadeItemDemandBucketFilterDto())


@SCENARIOS.register(SqlAlchemyBoughtItemDemandBucketRepository)
async def _bought_buckets(g: Graph, r: Any) -> None:
    await _buckets(r, await g.bought_bucket(), BoughtItemDemandBucketFilterDto())


@SCENARIOS.register(SqlAlchemySourceItemDemandBucketRepository)
async def _source_buckets(g: Graph, r: Any) -> None:
    await _buckets(r, await g.source_bucket(), SourceItemDemandBucketFilterDto())


@SCENARIOS.parametrize
async def test_read_methods_map_without_lazy_loads(repo_cls: type, db: AsyncSession) -> None:
    await SCENARIOS.run(repo_cls, db)
