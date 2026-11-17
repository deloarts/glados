"""
The planning read tools of the MCP surface over HTTP: explain_lot and its
`glados://lot/{number}` resource, the planning exceptions and the briefing,
each answering from a lot that waits on unallocated raw material.
"""

import json
from collections.abc import Awaitable
from collections.abc import Callable
from typing import Any

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.bootstrap.adapters.outbound.persistence.repositories.admin_settings_repository import (
    SqlAlchemyAdminSettingsRepository,
)
from src.modules.fulfillment.domain.entities.admin_settings.production import (
    AdminProductionSettings,
)
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.value_objects.permission import Permission
from tests.integration._mcp_helpers import call_tool
from tests.integration._mcp_helpers import mint_agent_token
from tests.integration._mcp_helpers import rpc
from tests.integration._mcp_helpers import save_agent_settings
from tests.integration.repository_reads._graph import Graph

# The graph builders write facts straight to the rows.
pytestmark = pytest.mark.usefixtures("allow_lifecycle_drift")


@pytest.fixture(autouse=True)
async def _seed_production_settings(db: AsyncSession) -> None:
    """The lot and schedule reads need the production settings, which the
    integration schema does not seed. Mirrors InitDatabase's defaults."""
    await SqlAlchemyAdminSettingsRepository(db).save_production(
        AdminProductionSettings(
            id=1,
            production_order_number_format="PON-{yy}-{seq:05d}",
            default_weekly_hours={0: 480, 1: 480, 2: 480, 3: 480, 4: 480, 5: 0, 6: 0},
            default_external_lead_days=0,
            response_time_days=1,
            require_qa=False,
        )
    )
    await db.commit()


@pytest.fixture
async def agent_owner(create_user: Callable[..., Awaitable[User]]) -> User:
    return await create_user(
        username="planner",
        email="planner@example.com",
        permissions=[Permission.WRITE_PAT, Permission.USE_MCP],
    )


@pytest.fixture
async def graph(db: AsyncSession, agent_owner: User, create_user: Any) -> Graph:
    other = await create_user(username="operator", email="operator@example.com")
    assert other.full_name
    return Graph(db, agent_owner, other)


@pytest.fixture
async def token(db: AsyncSession, agent_owner: User) -> str:
    await save_agent_settings(db)
    return await mint_agent_token(db, agent_owner, [Permission.USE_MCP])


async def _short_lot(graph: Graph) -> None:
    """Lot L-1 in production, with a made demand on it and a raw material
    demand no order line covers, so it is MATERIAL_SHORT."""
    await graph.source_demand()
    await graph.production_order()
    await graph.made_allocation()
    await graph.lot_event()


async def test_explain_lot_gathers_the_lot_its_demands_exceptions_and_events(
    client: httpx.AsyncClient, graph: Graph, token: str
) -> None:
    await _short_lot(graph)
    demand = await graph.made_demand()

    result = await call_tool(client, token, "explain_lot", {"number": "l-1"})

    assert result["isError"] is False, result["content"]
    data = result["structuredContent"]
    assert data["lot"]["lot_number"] == "L-1"
    assert "actions" not in data["lot"]
    assert [e["kind"] for e in data["planning_exceptions"]] == ["material_short"]
    [row] = data["demands"]
    assert (row["id"], row["allocated_quantity"]) == (demand.id, 5.0)
    assert [b["sequence"] for b in data["position_balances"]] == [1]
    assert data["events_total"] == len(data["events"])
    assert "created" in [e["summary"] for e in data["events"]]
    text = result["content"][0]["text"]
    assert graph.user.full_name not in text
    assert graph.other_user.full_name not in text


async def test_explain_lot_names_near_misses_of_an_unknown_number(
    client: httpx.AsyncClient, graph: Graph, token: str
) -> None:
    await graph.lot()

    result = await call_tool(client, token, "explain_lot", {"number": "L-"})

    assert result["isError"] is True
    assert "Similar numbers: L-1" in result["content"][0]["text"]


async def test_lot_resource_reads_through_explain_lot(
    client: httpx.AsyncClient, graph: Graph, token: str
) -> None:
    await graph.lot()

    response = await rpc(client, token, "resources/read", {"uri": "glados://lot/L-1"})

    assert response.status_code == 200, response.text
    [content] = response.json()["result"]["contents"]
    assert content["uri"] == "glados://lot/L-1"
    assert json.loads(content["text"])["lot"]["lot_number"] == "L-1"


async def test_list_planning_exceptions_filters_by_kind(
    client: httpx.AsyncClient, graph: Graph, token: str
) -> None:
    await _short_lot(graph)

    short = await call_tool(client, token, "list_planning_exceptions", {"kind": "material_short"})
    late = await call_tool(client, token, "list_planning_exceptions", {"kind": "late"})

    assert short["isError"] is False, short["content"]
    [row] = short["structuredContent"]["items"]
    assert (row["lot_number"], row["unallocated"]) == ("L-1", 10.0)
    assert late["structuredContent"] == {"total": 0, "items": []}


async def test_my_briefing_counts_exceptions_and_statuses(
    client: httpx.AsyncClient, graph: Graph, token: str
) -> None:
    await _short_lot(graph)

    result = await call_tool(client, token, "my_briefing", {"limit": 5})

    assert result["isError"] is False, result["content"]
    data = result["structuredContent"]
    assert data["planning_exceptions"]["by_kind"] == {"material_short": 1}
    assert sum(data["status_counts"]["lots"].values()) == 1
    assert set(data["todo"]) == {
        "orders",
        "bought_demands",
        "made_demands",
        "source_demands",
        "lots",
    }
    assert "spend" not in data
