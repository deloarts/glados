"""
Lot and production order numbers come from their families' counters: a
sequence that outgrows its padding keeps counting, and two draws never
return the same number even before either row is saved.
"""

from src.modules.fulfillment.adapters.outbound.persistence.repositories.production_lot_repository.lot import (
    SqlAlchemyProductionLotRepository,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.production_order_repository import (
    SqlAlchemyProductionOrderRepository,
)
from tests.integration.repository_reads._graph import Graph


async def test_lot_numbers_keep_counting_past_their_padding(db) -> None:
    graph = await Graph.seed(db)
    lot = await graph.lot()
    lots = SqlAlchemyProductionLotRepository(db)
    lot.lot_number = "LT9"
    await lots.save(lot)
    await db.commit()

    drawn = [await lots.next_lot_number("LT{seq}") for _ in range(2)]

    assert drawn == ["LT10", "LT11"]


async def test_production_order_numbers_keep_counting_past_their_padding(db) -> None:
    graph = await Graph.seed(db)
    order = await graph.production_order()
    orders = SqlAlchemyProductionOrderRepository(db)
    order.production_order_number = "PN9"
    await orders.save(order)
    await db.commit()

    drawn = [await orders.next_production_order_number("PN{seq}") for _ in range(2)]

    assert drawn == ["PN10", "PN11"]
