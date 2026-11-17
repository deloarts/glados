"""
Reads that follow the lifecycle facts of supplier order lines. A canceled
MADE line no longer supplies its lot position: once its order is canceled
the position shows no order line, and its whole quantity is open for
planning again. The delivery totals of a line are summed over its delivery
rows, with the lost pieces apart. Rows are seeded through the repository
read graph; the cancel goes through the API.
"""

from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.fulfillment.adapters.outbound.persistence.repositories.order_repository.delivery import (
    SqlAlchemyOrderItemDeliveryRepository,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.order_repository.order_item import (
    SqlAlchemyOrderItemRepository,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.production_lot_repository.lot import (
    SqlAlchemyProductionLotRepository,
)
from src.modules.fulfillment.domain.entities.lot_position import LotPosition
from src.modules.fulfillment.domain.entities.order_item_delivery import OrderItemDelivery
from src.modules.fulfillment.domain.services.lifecycle.delivery_totals import DeliveryTotals
from src.modules.fulfillment.domain.value_objects.rejection_outcome import RejectionOutcome
from src.modules.fulfillment.ports.outbound.repositories.production_lot_repository import (
    LotFilterDto,
)
from src.modules.platform.const import API_WEB
from src.modules.platform.domain.value_objects.permission import Permission
from tests.integration._edit_versions import order_version
from tests.integration.repository_reads._graph import NOW
from tests.integration.repository_reads._graph import Graph
from tests.integration.repository_reads._graph import make

ORDERS = f"{API_WEB}/orders"


async def _position(db: AsyncSession, lot_id: int, position_id: int) -> LotPosition:
    db.expire_all()
    lot = await SqlAlchemyProductionLotRepository(db).get_by_id(lot_id)
    assert lot is not None
    return next(p for p in lot.positions if p.id == position_id)


async def _lots_open_for_machines(db: AsyncSession) -> set[int]:
    _total, lots = await SqlAlchemyProductionLotRepository(db).get_multi(
        LotFilterDto(actionable_for="machines")
    )
    return {lot.id for lot in lots}


async def test_a_canceled_order_line_no_longer_holds_its_lot_position(
    db: AsyncSession, auth_client
) -> None:
    graph = await Graph.seed(db)
    lot = await graph.lot()
    line = await graph.made_order_item()
    assert line.lot_position_id is not None
    # The line covers the whole position, so nothing is left to plan.
    assert (await _position(db, lot.id, line.lot_position_id)).order_item_id == line.id
    assert await _lots_open_for_machines(db) == set()
    manager = await auth_client(
        permissions=[Permission.WRITE_ORDERS, Permission.MANAGE_ORDERS],
        username="buyer",
        email="buyer@example.com",
    )

    canceled = await manager.put(
        f"{ORDERS}/{line.order_id}/cancel",
        params={"expected_edit_version": await order_version(manager, line.order_id)},
    )

    assert canceled.status_code == 200, canceled.text
    position = await _position(db, lot.id, line.lot_position_id)
    assert (position.order_item_id, position.order_item_status) == (None, None)
    assert await _lots_open_for_machines(db) == {lot.id}


async def test_the_delivery_totals_sum_the_accepted_rejected_and_lost_pieces_per_line(
    db: AsyncSession,
) -> None:
    graph = await Graph.seed(db)
    await graph.delivery()  # Four pieces accepted on the bought line.
    bought = await graph.bought_order_item()
    source = await graph.source_order_item()
    deliveries = SqlAlchemyOrderItemDeliveryRepository(db)
    for accepted, rejected, outcome in (
        (1.0, 2.0, RejectionOutcome.LOST),
        (0.0, 1.0, RejectionOutcome.REDELIVER),
    ):
        await deliveries.save(
            make(
                OrderItemDelivery,
                order_item_id=bought.id,
                quantity=accepted,
                quantity_rejected=rejected,
                rejection_reason="supplier_damage",
                rejection_outcome=outcome,
                delivery_date=NOW,
                receiver_id=graph.uid,
            )
        )
    # The line's own totals follow its rows, as a booking keeps them.
    bought.quantity_delivered, bought.quantity_rejected, bought.quantity_rejected_lost = (
        5.0,
        3.0,
        2.0,
    )
    await SqlAlchemyOrderItemRepository(db).save(bought)
    await db.commit()

    totals = await deliveries.get_totals_by_order_item_ids([bought.id, source.id])

    # The source line has no rows and therefore no entry.
    assert totals == {bought.id: DeliveryTotals(accepted=5.0, rejected=3.0, lost=2.0)}
