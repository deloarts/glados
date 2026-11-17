"""
The supply and shop floor read tools of the MCP surface over HTTP: demand
coverage of a project or a part, supplier orders with overdue lines, the
offers of a quote request side by side, the schedule board and the work in
progress. Money stays out of every answer unless the agent settings let
costs in.
"""

from collections.abc import Awaitable
from collections.abc import Callable
from dataclasses import replace
from datetime import timedelta
from typing import Any

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.bootstrap.adapters.outbound.persistence.repositories.admin_settings_repository import (
    SqlAlchemyAdminSettingsRepository,
)
from src.modules.catalogue.domain.value_objects.bought_item_status import BoughtItemDemandStatus
from src.modules.fulfillment.adapters.outbound.persistence.repositories.bought_item_repository.demand_item import (
    SqlAlchemyBoughtItemDemandItemRepository,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.order_repository.order_item import (
    SqlAlchemyOrderItemRepository,
)
from src.modules.fulfillment.domain.entities.admin_settings.production import (
    AdminProductionSettings,
)
from src.modules.platform.const import API_WEB
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.value_objects.permission import Permission
from tests.integration._mcp_helpers import call_tool
from tests.integration._mcp_helpers import mint_agent_token
from tests.integration._mcp_helpers import save_agent_settings
from tests.integration.repository_reads._graph import TODAY
from tests.integration.repository_reads._graph import Graph

# The graph builders write facts straight to the rows.
pytestmark = pytest.mark.usefixtures("allow_lifecycle_drift")

RFQ = f"{API_WEB}/quote-requests"


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
    other = await create_user(username="receiver", email="receiver@example.com")
    return Graph(db, agent_owner, other)


@pytest.fixture
async def token(db: AsyncSession, agent_owner: User) -> str:
    await save_agent_settings(db)
    return await mint_agent_token(db, agent_owner, [Permission.USE_MCP])


async def _data(client: httpx.AsyncClient, token: str, tool: str, **arguments: Any) -> Any:
    result = await call_tool(client, token, tool, arguments)
    assert result["isError"] is False, result["content"]
    return result["structuredContent"]


# ── demand_coverage ──────────────────────────────────────────────────────


async def test_demand_coverage_of_a_project_reads_every_family(
    client: httpx.AsyncClient, graph: Graph, token: str
) -> None:
    bought = await graph.bought_allocation()
    made = await graph.made_allocation()
    source = await graph.source_demand()

    data = await _data(client, token, "demand_coverage", project_number="P-1")

    [bought_row] = data["bought"]["items"]
    assert (bought_row["id"], bought_row["item_part_number"]) == (bought.demand_item_id, "B-1")
    assert bought_row["coverage"]["allocated"] == 5.0
    assert bought_row["coverage"]["order_numbers"] == ["O-1"]
    [made_row] = data["made"]["items"]
    assert (made_row["id"], made_row["coverage"]["lot_ids"]) == (made.demand_item_id, [made.lot_id])
    [source_row] = data["source"]["items"]
    assert (source_row["id"], source_row["lot_number"]) == (source.id, "L-1")
    assert source_row["coverage"]["unallocated"] == 10.0


async def test_demand_coverage_of_a_part_leaves_raw_material_out(
    client: httpx.AsyncClient, graph: Graph, token: str
) -> None:
    await graph.made_allocation()
    await graph.bought_demand()

    data = await _data(client, token, "demand_coverage", part_number="M-1")
    refused = await call_tool(client, token, "demand_coverage", {})

    assert (data["made"]["total"], data["bought"]["total"]) == (1, 0)
    assert "source" not in data
    assert refused["isError"] is True


# ── orders ───────────────────────────────────────────────────────────────


async def test_orders_overdue_only_lists_the_late_line_without_prices(
    client: httpx.AsyncClient, graph: Graph, token: str
) -> None:
    line = await graph.bought_order_item()
    lines = SqlAlchemyOrderItemRepository(graph.db)
    await lines.save(replace(line, expected_delivery_date=TODAY - timedelta(days=3), price=1200))
    await graph.db.commit()

    overdue = await _data(client, token, "orders", overdue_only=True)
    listed = await _data(client, token, "orders", order_number="O-1")

    [order] = overdue["items"]
    assert order["order_number"] == "O-1"
    [row] = order["lines"]
    assert row["overdue"] is True
    assert "price" not in row
    assert "net_total" not in order
    assert listed["total"] == 1


async def test_orders_overdue_only_skips_a_line_due_today(
    client: httpx.AsyncClient, graph: Graph, token: str
) -> None:
    await graph.bought_order_item()

    data = await _data(client, token, "orders", overdue_only=True)

    assert data == {"total": 0, "items": []}


# ── compare_offers ───────────────────────────────────────────────────────


async def _quoted_request(graph: Graph, auth_client: Any) -> str:
    """A sent quote request for one bought line, which the supplier priced
    at 3.00 with a lead time."""
    buyer = await auth_client(
        username="buyer",
        email="buyer@example.com",
        permissions=[Permission.WRITE_ORDERS, Permission.MANAGE_ORDERS],
    )
    template = await graph.bought_demand()
    demand = await SqlAlchemyBoughtItemDemandItemRepository(graph.db).save(
        replace(template, id=0, quantity=4.0, status=BoughtItemDemandStatus.OPEN, changes=[])
    )
    await graph.db.commit()
    line = {
        "bought_item_id": (await graph.bought_item()).id,
        "project_id": (await graph.project()).id,
        "quantity": 4.0,
        "unit": "pcs",
        "demands": [{"family": "bought", "demand_item_id": demand.id, "quantity": 4.0}],
    }
    created = await buyer.post(
        f"{RFQ}/", json={"supplier_ids": [(await graph.supplier()).id], "lines": [line]}
    )
    assert created.status_code == 201, created.text
    request = created.json()
    [row] = request["suppliers"]
    sent = await buyer.post(f"{RFQ}/{request['id']}/suppliers/{row['id']}/sent")
    assert sent.status_code == 200, sent.text
    offer = {
        "quotes": [{"line_id": request["lines"][0]["id"], "unit_price": 300, "lead_time_days": 5}]
    }
    priced = await buyer.put(f"{RFQ}/{request['id']}/suppliers/{row['id']}/offer", json=offer)
    assert priced.status_code == 200, priced.text
    return str(request["request_number"])


async def test_compare_offers_shows_each_supplier_answer_per_line(
    client: httpx.AsyncClient, db: AsyncSession, graph: Graph, token: str, auth_client: Any
) -> None:
    number = await _quoted_request(graph, auth_client)

    listed = await _data(client, token, "compare_offers")
    hidden = await _data(client, token, "compare_offers", request_number=number)
    await save_agent_settings(db, include_costs=True)
    shown = await _data(client, token, "compare_offers", request_number=number)

    assert [r["request_number"] for r in listed["items"]] == [number]
    assert listed["items"][0]["responded_count"] == 1
    [line] = hidden["lines"]
    [offer] = line["offers"]
    assert (offer["supplier_name"], offer["lead_time_days"]) == ("Acme", 5)
    assert "unit_price" not in offer
    assert "total_price" not in hidden["suppliers"][0]
    assert shown["lines"][0]["offers"][0]["unit_price"] == 300
    assert shown["suppliers"][0]["total_price"] == 1200


# ── schedule and shop floor ──────────────────────────────────────────────


async def test_schedule_lists_the_machine_with_its_production_order(
    client: httpx.AsyncClient, graph: Graph, token: str
) -> None:
    await graph.production_order()

    board = await _data(client, token, "schedule", days=3)
    one = await _data(client, token, "schedule", days=3, machine="mill")
    refused = await call_tool(client, token, "schedule", {"machine": "MILL", "pool": "Mills"})

    [machine] = board["machines"]
    assert machine["machine_internal_name"] == "MILL-1"
    assert [o["production_order_number"] for o in machine["orders"]["items"]] == ["PO-1"]
    assert "unassigned" in board
    assert (len(one["machines"]), one["pools"]) == (1, [])
    assert "unassigned" not in one
    assert refused["isError"] is True


async def test_shop_floor_now_lists_the_lot_in_work(
    client: httpx.AsyncClient, graph: Graph, token: str
) -> None:
    await graph.production_order()

    data = await _data(client, token, "shop_floor_now")

    [lot] = data["work_in_progress"]["items"]
    assert lot["lot_number"] == "L-1"
    assert [s["machine_names"] for s in lot["stages"]] == [["MILL-1"]]
    assert data["qa_tasks"] == {"total": 0, "items": []}
