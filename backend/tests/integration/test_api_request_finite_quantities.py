"""
A non-finite quantity in a request body is refused with 422 before any use
case runs, for every family that books quantities: bought, made and source
demands and allocations, lots and production orders. JSON as FastAPI parses
it accepts NaN, Infinity and overflowing literals such as 1e999, so the
request schemas refuse them (allow_inf_nan=False). A quantity the NUMERIC(18, 6)
columns cannot store, one that rounds to zero at six decimals or one of 10**12
or more, is refused the same way, in the body and in a delivery's query. The
ids in the paths and bodies need not exist, because the body is validated
first.
"""

import pytest

from src.modules.platform.domain.value_objects.permission import Permission
from tests.integration.repository_reads._graph import Graph

JSON = {"Content-Type": "application/json"}
WEB = "/api/v1/web"

PERMISSIONS = [
    Permission.WRITE_ALLOCATIONS,
    Permission.WRITE_DEMAND_ITEMS,
    Permission.MANAGE_DEMAND_ITEMS,
    Permission.WRITE_LOTS,
    Permission.MANAGE_LOTS,
    Permission.WRITE_PRODUCTION_ORDERS,
    Permission.MANAGE_PRODUCTION_ORDERS,
    Permission.WRITE_INSPECTIONS,
]

REQUESTS = [
    (
        "bought-items-demands/",
        '{"item_id": 1, "project_id": 1, "quantity": %s, "unit": "pcs"}',
        ["body", "quantity"],
    ),
    (
        "bought-items-allocations/",
        '{"demand_item_id": 1, "order_item_id": 1, "quantity": %s}',
        ["body", "quantity"],
    ),
    (
        "made-items-demands/",
        '{"made_item_id": 1, "project_id": 1, "quantity": 2, "unit": "pcs", "items_per_unit": %s}',
        ["body", "items_per_unit"],
    ),
    (
        "made-items-allocations/demand/1/fulfill-from-stock",
        '{"quantity": %s}',
        ["body", "quantity"],
    ),
    ("source-item-demands/", '{"lot_id": 1, "quantity": %s}', ["body", "quantity"]),
    (
        "source-item-allocations/",
        '{"demand_item_id": 1, "order_item_id": 1, "quantity": %s}',
        ["body", "quantity"],
    ),
    (
        "production-lots/",
        '{"made_item_id": 1, "project_id": 1, "quantity": %s}',
        ["body", "quantity"],
    ),
    (
        "production-lots/1/scrap",
        '{"position_id": 1, "quantity": %s, "reason": "tool_breakage", "expected_edit_version": 0}',
        ["body", "quantity"],
    ),
    (
        "production-orders/1/completions",
        '{"quantity": 2, "quantity_accepted": %s}',
        ["body", "quantity_accepted"],
    ),
    ("production-orders/1/split", '{"quantities": [1, %s]}', ["body", "quantities", 1]),
]


@pytest.mark.parametrize(("path", "body", "loc"), REQUESTS, ids=[r[0] for r in REQUESTS])
@pytest.mark.parametrize("literal", ["NaN", "Infinity", "1e999"])
async def test_a_non_finite_quantity_in_the_body_returns_422(
    auth_client, path: str, body: str, loc: list[object], literal: str
) -> None:
    client = await auth_client(permissions=PERMISSIONS)

    response = await client.post(f"{WEB}/{path}", content=body % literal, headers=JSON)

    assert response.status_code == 422, response.text
    errors = response.json()["detail"]
    assert any(e["loc"] == loc and e["type"] == "finite_number" for e in errors), errors


STORED_QUANTITY_REQUESTS = [r for r in REQUESTS if r[2][-1] != "items_per_unit"]


@pytest.mark.parametrize(
    ("path", "body", "loc"), STORED_QUANTITY_REQUESTS, ids=[r[0] for r in STORED_QUANTITY_REQUESTS]
)
@pytest.mark.parametrize("literal", ["0.0000004", "1e12", "999999999999.9999999"])
async def test_a_quantity_the_columns_cannot_store_returns_422(
    auth_client, path: str, body: str, loc: list[object], literal: str
) -> None:
    client = await auth_client(permissions=PERMISSIONS)

    response = await client.post(f"{WEB}/{path}", content=body % literal, headers=JSON)

    assert response.status_code == 422, response.text
    assert any(e["loc"] == loc for e in response.json()["detail"]), response.text


@pytest.mark.parametrize("literal", ["0.0000004", "1e12"])
async def test_a_delivery_quantity_the_columns_cannot_store_returns_422(
    auth_client, literal: str
) -> None:
    client = await auth_client(permissions=[Permission.RECEIVE_DELIVERIES])

    response = await client.put(
        f"{WEB}/bought-items-allocations/order-item/1/deliver", params={"quantity": literal}
    )

    assert response.status_code == 422, response.text
    assert any(e["loc"] == ["query", "quantity"] for e in response.json()["detail"])


async def test_a_quantity_the_lifecycle_counts_as_nothing_returns_422(
    db, auth_client, create_user
) -> None:
    """0.000001 is stored as it is, but every lifecycle comparison takes
    quantities within 0.000001 of each other as equal, so a demand of it
    would read fulfilled with nothing allocated."""
    client = await auth_client(permissions=PERMISSIONS)
    owner = await create_user(username="owner", email="owner@example.com")
    graph = Graph(db, owner, owner)
    item = await graph.bought_item()
    project = await graph.project()

    response = await client.post(
        f"{WEB}/bought-items-demands/",
        json={"item_id": item.id, "project_id": project.id, "quantity": 0.000001, "unit": "m"},
    )

    assert response.status_code == 422, response.text
