"""
A second cancel of a bought or made item demand answers 409 with
DemandItemAlreadyCanceledError through HTTP, the same in both families, and
leaves the demand canceled.
"""

from typing import Any

import pytest

from src.modules.platform.const import API_WEB
from src.modules.platform.domain.value_objects.permission import Permission
from tests.integration.conftest import auth_headers
from tests.integration.repository_reads._graph import Graph

ROUTES = {
    "bought": f"{API_WEB}/bought-items-demands",
    "made": f"{API_WEB}/made-items-demands",
}


@pytest.mark.parametrize("family", ["bought", "made"])
async def test_a_second_cancel_answers_409_in_both_families(
    family: str, client: Any, db: Any, create_user: Any
) -> None:
    manager = await create_user(
        username="manager",
        email="manager@example.com",
        permissions=[Permission.WRITE_DEMAND_ITEMS, Permission.MANAGE_DEMAND_ITEMS],
    )
    graph = Graph(db, manager, manager)
    demand = await (graph.bought_demand() if family == "bought" else graph.made_demand())
    await db.commit()
    url = f"{ROUTES[family]}/{demand.id}"
    headers = await auth_headers(manager)

    first = await client.post(f"{url}/cancel", headers=headers)
    assert first.status_code == 200, first.text
    assert first.json()["status"] == "canceled"

    second = await client.post(f"{url}/cancel", headers=headers)

    assert second.status_code == 409, second.text
    assert second.json()["code"] == "DemandItemAlreadyCanceledError"
    stored = await client.get(url, headers=headers)
    assert stored.json()["status"] == "canceled"
