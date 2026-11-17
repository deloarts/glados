"""
A quantity that counts pieces is a whole number. A lot of 2.5 pieces is
refused with 422 and the code FractionalPiecesError, and so is a bought item
demand of 2.5 in a unit that counts whole things, while the same demand in
metres is created.
"""

from typing import Any

import pytest

from src.modules.platform.const import API_WEB
from src.modules.platform.domain.value_objects.permission import Permission
from tests.integration.repository_reads._graph import Graph

PERMISSIONS = [Permission.WRITE_LOTS, Permission.WRITE_DEMAND_ITEMS]


@pytest.fixture
async def graph(db: Any, create_user: Any) -> Graph:
    user = await create_user(username="creator", email="creator@example.com")
    other = await create_user(username="operator", email="operator@example.com")
    return Graph(db, user, other)


@pytest.fixture
async def client(auth_client: Any) -> Any:
    return await auth_client(
        username="planner", email="planner@example.com", permissions=PERMISSIONS
    )


async def test_a_lot_of_fractional_pieces_is_refused(graph: Graph, client: Any) -> None:
    made_item = await graph.made_item()
    project = await graph.project()

    response = await client.post(
        f"{API_WEB}/production-lots/",
        json={"made_item_id": made_item.id, "project_id": project.id, "quantity": 2.5},
    )

    assert response.status_code == 422, response.text
    assert response.json()["code"] == "FractionalPiecesError"


@pytest.mark.parametrize(("unit", "status"), [("PCS", 422), ("SET", 422), ("M", 201)])
async def test_a_demand_of_a_fraction_needs_a_measured_unit(
    graph: Graph, client: Any, unit: str, status: int
) -> None:
    item = await graph.bought_item()
    project = await graph.project()

    response = await client.post(
        f"{API_WEB}/bought-items-demands/",
        json={"item_id": item.id, "project_id": project.id, "quantity": 2.5, "unit": unit},
    )

    assert response.status_code == status, response.text
    if status == 422:
        assert response.json()["code"] == "FractionalPiecesError"
