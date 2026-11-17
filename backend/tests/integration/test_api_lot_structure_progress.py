"""
A structure edit leaves a position with physical history alone: a position
whose only production order was canceled after it booked scrap has nothing
completed and reads as unassigned, yet its completion row is progress, so
deleting its last step, which would delete the position with the row, is
refused.
"""

from datetime import UTC
from datetime import datetime
from typing import Any

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.fulfillment.adapters.outbound.persistence.lifecycle_store import (
    sql_lifecycle_repositories,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.production_order_model import (
    ProductionOrderOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.production_order_repository import (
    SqlAlchemyProductionOrderRepository,
)
from src.modules.fulfillment.application.services.lifecycle_reconciler import LifecycleReconciler
from src.modules.fulfillment.domain.entities.production_order_completion import (
    ProductionOrderCompletion,
)
from src.modules.platform.const import API_WEB
from src.modules.platform.domain.value_objects.permission import Permission
from tests.integration._lot_facts import _SEEDER
from tests.integration.repository_reads._graph import Graph
from tests.integration.repository_reads._graph import make

LOTS = f"{API_WEB}/production-lots"


class _NoBus:
    async def publish(self, event: object) -> None:
        return None


async def test_lot_structure_keeps_a_position_whose_canceled_order_booked_scrap(
    db: AsyncSession, create_user: Any, auth_client: Any
) -> None:
    owner = await create_user(username="owner", email="owner@example.com")
    graph = Graph(db, owner, owner)
    order = await graph.production_order()
    await graph.external_position()
    await SqlAlchemyProductionOrderRepository(db).save_completion(
        make(
            ProductionOrderCompletion,
            production_order_id=order.id,
            quantity=2.0,
            quantity_accepted=0.0,
            quantity_rejected=2.0,
            quantity_scrap=2.0,
            operator_id=owner.id,
            recorded_by_id=owner.id,
        )
    )
    await db.execute(
        update(ProductionOrderOrmModel)
        .where(ProductionOrderOrmModel.id == order.id)
        .values(canceled_at=datetime.now(UTC), planned_start=None, planned_end=None)
    )
    await db.commit()
    reconciler = LifecycleReconciler(sql_lifecycle_repositories(db), _NoBus())
    reconciler.touch_production_orders([order.id])
    await reconciler.run(_SEEDER, datetime.now(UTC), reason="seeded")
    await db.commit()
    client = await auth_client(permissions=[Permission.WRITE_LOTS, Permission.MANAGE_LOTS])
    lot = (await client.get(f"{LOTS}/{(await graph.lot()).id}")).json()
    first = next(p for p in lot["positions"] if p["sequence"] == 1)
    assert (first["kind"], first["quantity_completed"]) == ("unassigned", 0.0)

    deleted = await client.delete(f"{LOTS}/{lot['id']}/steps/{first['steps'][0]['id']}")

    assert deleted.status_code == 409, deleted.text
    assert deleted.json()["code"] == "LotPositionAlreadyAssignedError"
    after = (await client.get(f"{LOTS}/{lot['id']}")).json()
    assert [p["id"] for p in after["positions"]] == [p["id"] for p in lot["positions"]]
