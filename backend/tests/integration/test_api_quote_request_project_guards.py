"""
A quote request line is work on its project, which a project on hold takes
no more of: adding a line, replacing a line with one for another item and
taking a dropped line back are refused there with 409, while dropping a line
stays allowed, since it only cleans up. Each of these writers share-locks
the line's project before it locks the request, so a project being
completed or archived counts the line or refuses it.
"""

from typing import Any

import pytest
from sqlalchemy import update

from src.modules.workspace.adapters.outbound.persistence.models.project_model import ProjectOrmModel
from tests.integration.repository_reads._graph import Graph
from tests.integration.test_api_quote_requests import BUYER
from tests.integration.test_api_quote_requests import RFQ
from tests.integration.test_api_quote_requests import _bought_line
from tests.integration.test_api_quote_requests import _open_demand
from tests.integration.test_api_quote_requests import _other_bought_item
from tests.integration.test_api_quote_requests import _request


@pytest.fixture
async def graph(db: Any, create_user: Any) -> Graph:
    user = await create_user(username="creator", email="creator@example.com")
    other = await create_user(username="receiver", email="receiver@example.com")
    return Graph(db, user, other)


@pytest.fixture
async def buyer(auth_client: Any) -> Any:
    return await auth_client(username="buyer", email="buyer@example.com", permissions=BUYER)


async def _hold_project(graph: Graph) -> None:
    project = await graph.project()
    await graph.db.execute(
        update(ProjectOrmModel).where(ProjectOrmModel.id == project.id).values(status="on_hold")
    )
    await graph.db.commit()


async def _two_line_request(graph: Graph, buyer: Any) -> dict:
    first = await _open_demand(graph, 2.0)
    second = await _open_demand(graph, 3.0)
    supplier = await graph.supplier()
    return await _request(
        buyer,
        graph,
        [await _bought_line(graph, 2.0, first, 2.0), await _bought_line(graph, 3.0, second, 3.0)],
        [supplier.id],
    )


async def test_a_line_on_a_project_on_hold_is_dropped_but_not_taken_back(
    graph: Graph, buyer: Any
) -> None:
    request = await _two_line_request(graph, buyer)
    line_id = request["lines"][0]["id"]
    await _hold_project(graph)

    dropped = await buyer.post(f"{RFQ}/{request['id']}/lines/{line_id}/drop")
    restored = await buyer.post(f"{RFQ}/{request['id']}/lines/{line_id}/restore")

    assert dropped.status_code == 200, dropped.text
    assert restored.status_code == 409, restored.text
    assert restored.json()["code"] == "ProjectInactiveError"


async def test_a_line_on_a_project_on_hold_is_not_replaced(graph: Graph, buyer: Any) -> None:
    request = await _two_line_request(graph, buyer)
    line_id = request["lines"][0]["id"]
    alternative = await _other_bought_item(graph)
    await _hold_project(graph)

    replaced = await buyer.post(
        f"{RFQ}/{request['id']}/lines/{line_id}/substitute", json={"bought_item_id": alternative}
    )

    assert replaced.status_code == 409, replaced.text
    assert replaced.json()["code"] == "ProjectInactiveError"


async def test_no_line_is_added_for_a_project_on_hold(graph: Graph, buyer: Any) -> None:
    request = await _two_line_request(graph, buyer)
    demand = await _open_demand(graph, 1.0)
    line = await _bought_line(graph, 1.0, demand, 1.0)
    await _hold_project(graph)

    added = await buyer.post(f"{RFQ}/{request['id']}/lines", json={"lines": [line]})

    assert added.status_code == 409, added.text
    assert added.json()["code"] == "ProjectInactiveError"
