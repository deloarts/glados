"""
The grouped capacity read answers what the single-line read answers for
every order item it is given: the bought and the source allocations on the
line together, and 0.0 for a line without any.
"""

from src.modules.fulfillment.adapters.outbound.persistence.repositories.bought_item_repository.allocation import (
    SqlAlchemyBoughtItemAllocationRepository,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.source_item_allocation_repository import (
    SqlAlchemySourceItemAllocationRepository,
)
from tests.integration.repository_reads._graph import Graph

_NO_LINE = 999_999


async def test_the_grouped_read_matches_the_single_line_read(db) -> None:
    graph = await Graph.seed(db)
    bought = await graph.bought_allocation()
    source = await graph.source_allocation()
    assert bought.order_item_id is not None and source.order_item_id is not None
    line_ids = [bought.order_item_id, source.order_item_id, _NO_LINE]

    for repo in (
        SqlAlchemyBoughtItemAllocationRepository(db),
        SqlAlchemySourceItemAllocationRepository(db),
    ):
        grouped = await repo.get_allocated_quantities_for_order_items(line_ids)

        assert grouped == {
            line_id: await repo.get_allocated_quantity_for_order_item(line_id)
            for line_id in line_ids
        }
        assert grouped[bought.order_item_id] > 0
        assert grouped[_NO_LINE] == 0.0
