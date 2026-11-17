"""
A delivery records where the received material comes from, its batch or
heat number, delivery note and certificate, and the lot whose raw material
the line supplies lists that receipt as its material genealogy. A lot also
balances the pieces of each position.
"""

from typing import Any

import pytest

from src.modules.platform.const import API_WEB
from src.modules.platform.domain.value_objects.permission import Permission
from tests.integration.repository_reads._graph import Graph

DELIVER = f"{API_WEB}/bought-items-allocations/order-item"
LOTS = f"{API_WEB}/production-lots"


@pytest.fixture
async def graph(db: Any, create_user: Any) -> Graph:
    user = await create_user(username="creator", email="creator@example.com")
    other = await create_user(username="operator", email="operator@example.com")
    return Graph(db, user, other)


async def test_a_receipt_s_batch_and_certificate_reach_the_lot_that_consumes_it(
    graph: Graph, auth_client: Any
) -> None:
    allocation = await graph.source_allocation()
    lot = await graph.lot()
    receiver = await auth_client(
        username="receiver",
        email="receiver@example.com",
        permissions=[Permission.RECEIVE_DELIVERIES],
    )

    delivered = await receiver.put(
        f"{DELIVER}/{allocation.order_item_id}/deliver",
        params={"quantity": 5},
        json={
            "supplier_batch": " H-4711 ",
            "delivery_note_number": "LS-2026-118",
            "certificate_reference": "3.1-99812",
        },
    )
    assert delivered.status_code == 200, delivered.text

    receipts = await receiver.get(f"{LOTS}/{lot.id}/material-receipts")

    assert receipts.status_code == 200, receipts.text
    [receipt] = receipts.json()
    assert receipt["order_item_id"] == allocation.order_item_id
    assert (
        receipt["quantity"],
        receipt["supplier_batch"],
        receipt["delivery_note_number"],
        receipt["certificate_reference"],
    ) == (5.0, "H-4711", "LS-2026-118", "3.1-99812")


async def test_a_lot_without_raw_material_has_no_receipts(graph: Graph, auth_client: Any) -> None:
    lot = await graph.lot()
    reader = await auth_client(username="reader", email="reader@example.com", permissions=[])

    receipts = await reader.get(f"{LOTS}/{lot.id}/material-receipts")

    assert receipts.status_code == 200, receipts.text
    assert receipts.json() == []


async def test_each_position_of_a_lot_balances_its_pieces(graph: Graph, auth_client: Any) -> None:
    lot = await graph.full_lot()
    reader = await auth_client(username="balance", email="balance@example.com", permissions=[])

    response = await reader.get(f"{LOTS}/{lot.id}/position-balances")

    assert response.status_code == 200, response.text
    balances = response.json()
    assert [b["position_id"] for b in balances] == [
        p.id for p in sorted(lot.positions, key=lambda p: p.sequence)
    ]
    for b in balances:
        accounted = b["good"] + b["scrap"] + b["rework"] + b["lost"] + b["wip"]
        assert abs(b["arrived"] - accounted - b["difference"]) < 1e-9, b
        assert b["produced"] == b["good"] + b["scrap"]
