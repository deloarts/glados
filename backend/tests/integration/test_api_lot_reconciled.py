"""
Lots over HTTP on the throwaway SQLite file, with the lifecycle reconciler
deriving every lot and position status from the recorded facts and intents
and the drift check after each test confirming that the stored ones match:
a delivery on a held lot keeps it ON_HOLD until it is resumed, a scrap at
position 2 shrinks the lot and later position until everything completes,
the live WIP view counts no negative raw pieces after it, and a full scrap
leaves a SCRAPPED lot.
"""

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.fulfillment.adapters.outbound.persistence.models.lot_position_model import (
    LotPositionOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.production_lot_repository.lot import (
    SqlAlchemyProductionLotRepository,
)
from src.modules.fulfillment.domain.entities.lot_position import LotPosition
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionKind
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionStatus
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.value_objects.permission import Permission
from tests.integration._edit_versions import lot_version
from tests.integration._tenant_day import tenant_today
from tests.integration.conftest import auth_headers
from tests.integration.repository_reads._graph import Graph
from tests.integration.repository_reads._graph import make
from tests.integration.test_api_production_order_reconciled import ORDERS
from tests.integration.test_api_production_order_reconciled import _Floor
from tests.integration.test_api_production_order_reconciled import _floor
from tests.integration.test_api_production_order_reconciled import _post
from tests.integration.test_api_production_order_reconciled import _seed_production_settings  # noqa: F401
from tests.integration.test_api_production_order_reconciled import planner  # noqa: F401

LOTS = "/api/v1/web/production-lots"
DELIVER_URL = "/api/v1/web/bought-items-allocations/order-item"
WIP = "/api/v1/web/production-wip/"


async def _lot(client: Any, lot_id: int, user: User) -> dict[str, Any]:
    response = await client.get(f"{LOTS}/{lot_id}", headers=await auth_headers(user))
    assert response.status_code == 200, response.text
    return dict(response.json())


async def _second_position(db: AsyncSession, floor: _Floor) -> int:
    """A second internal position after the floor's own, 10 pieces."""
    position = await SqlAlchemyProductionLotRepository(db).save_position(
        make(
            LotPosition,
            sequence=2,
            kind=LotPositionKind.INTERNAL,
            status=LotPositionStatus.ORDERED_OR_QUEUED,
            quantity=10.0,
            quantity_completed=0.0,
            creator_id=floor.creator_id,
            lot_id=floor.lot_id,
        )
    )
    await db.commit()
    return position.id


async def _order_at(floor: _Floor, position_id: int, quantity: float, sequence: int) -> int:
    own, floor.position_id = floor.position_id, position_id
    try:
        return await floor.order(quantity, sequence)
    finally:
        floor.position_id = own


async def _complete(client: Any, order_id: int, user: User, quantity: float) -> None:
    done = await _post(
        client,
        f"{ORDERS}/{order_id}/completions",
        user,
        {"quantity": quantity, "completion_date": tenant_today().isoformat()},
    )
    assert done.status_code == 200, done.text


async def _scrap(client: Any, order_id: int, user: User, quantity: float) -> None:
    headers = await auth_headers(user)
    order = await client.get(f"{ORDERS}/{order_id}", headers=headers)
    scrapped = await _post(
        client,
        f"{ORDERS}/{order_id}/scrap",
        user,
        {
            "quantity": quantity,
            "reason": "tool_breakage",
            "create_replacement": False,
            "expected_edit_version": order.json()["edit_version"],
            "expected_lot_edit_version": await lot_version(client, order.json()["lot_id"], headers),
        },
    )
    assert scrapped.status_code == 200, scrapped.text


async def test_a_delivery_on_a_held_lot_keeps_it_on_hold_until_it_is_resumed(
    db: AsyncSession, auth_client: Any
) -> None:
    graph = await Graph.seed(db)
    lot = await graph.lot()
    line = await graph.made_order_item()
    # The lot's only position, so it is the first.
    position = await db.get(LotPositionOrmModel, line.lot_position_id)
    assert position is not None
    position.sequence = 1
    await db.commit()
    planner_client = await auth_client(
        permissions=[Permission.WRITE_LOTS], username="holder", email="holder@example.com"
    )
    receiver = await auth_client(
        permissions=[Permission.RECEIVE_DELIVERIES],
        username="receiver",
        email="receiver@example.com",
    )

    held = await planner_client.post(f"{LOTS}/{lot.id}/hold", json={"reason": "Drawing check"})
    assert held.status_code == 200, held.text
    received = await receiver.put(f"{DELIVER_URL}/{line.id}/deliver", params={"quantity": 4.0})
    assert received.status_code == 200, received.text

    body = (await planner_client.get(f"{LOTS}/{lot.id}")).json()
    assert body["status"] == "on_hold"
    assert [(p["status"], p["quantity_completed"]) for p in body["positions"]] == [
        ("partially_completed", 4.0)
    ]

    resumed = await planner_client.post(f"{LOTS}/{lot.id}/resume", json={})
    assert resumed.status_code == 200, resumed.text
    assert resumed.json()["status"] == "in_progress"


async def test_a_scrap_at_position_two_shrinks_the_rest_and_everything_completes(
    db: AsyncSession,
    client: Any,
    planner: User,  # noqa: F811
) -> None:
    floor = await _floor(db, planner)
    second = await _second_position(db, floor)
    first_order = await _order_at(floor, floor.position_id, 10.0, 1)
    second_order = await _order_at(floor, second, 10.0, 2)
    for order_id in (first_order, second_order):
        started = await _post(client, f"{ORDERS}/{order_id}/start", planner)
        assert started.status_code == 200, started.text
        if order_id == first_order:
            await _complete(client, first_order, planner, 10.0)

    await _scrap(client, second_order, planner, 2.0)

    body = await _lot(client, floor.lot_id, planner)
    assert body["quantity"] == 8.0
    assert [(p["quantity"], p["quantity_completed"]) for p in body["positions"]] == [
        (10.0, 10.0),
        (8.0, 0.0),
    ]
    wip = await client.get(WIP, headers=await auth_headers(planner))
    assert wip.status_code == 200, wip.text
    [row] = [r for r in wip.json() if r["id"] == floor.lot_id]
    assert (row["raw_count"], row["finished_count"]) == (0.0, 0.0)

    await _complete(client, second_order, planner, 8.0)

    body = await _lot(client, floor.lot_id, planner)
    assert body["status"] == "completed"
    assert [p["status"] for p in body["positions"]] == ["completed", "completed"]


async def test_a_full_scrap_leaves_a_scrapped_lot(
    db: AsyncSession,
    client: Any,
    planner: User,  # noqa: F811
) -> None:
    floor = await _floor(db, planner)
    order_id = await floor.order(10.0, 1)
    started = await _post(client, f"{ORDERS}/{order_id}/start", planner)
    assert started.status_code == 200, started.text

    await _scrap(client, order_id, planner, 10.0)

    body = await _lot(client, floor.lot_id, planner)
    assert (body["quantity"], body["status"]) == (0.0, "scrapped")
