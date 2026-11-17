"""
The workspace tools of the MCP surface over HTTP: a project's status by
its number, a product's status with its device completeness, and what
renumbering a product would affect. Projects, products and devices are
created through the web API.
"""

from collections.abc import Awaitable
from collections.abc import Callable
from typing import Any

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.platform.const import API_WEB
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.value_objects.permission import Permission
from tests.integration._mcp_helpers import call_tool
from tests.integration._mcp_helpers import mint_agent_token
from tests.integration._mcp_helpers import save_agent_settings

RESOURCES = f"{API_WEB}/product-device-resources"


@pytest.fixture(autouse=True)
async def agents_on(db: AsyncSession) -> None:
    await save_agent_settings(db)


@pytest.fixture
async def agent_owner(create_user: Callable[..., Awaitable[User]]) -> User:
    return await create_user(
        username="planner",
        email="planner@example.com",
        permissions=[Permission.WRITE_PAT, Permission.USE_MCP],
    )


@pytest.fixture
async def token(db: AsyncSession, agent_owner: User) -> str:
    return await mint_agent_token(db, agent_owner, [Permission.USE_MCP])


@pytest.fixture
async def manager(auth_client: Any) -> httpx.AsyncClient:
    c: httpx.AsyncClient = await auth_client(
        username="manager",
        email="manager@example.com",
        permissions=[
            Permission.WRITE_PROJECTS,
            Permission.MANAGE_PROJECTS,
            Permission.WRITE_PRODUCT_DEVICE_RESOURCES,
        ],
    )
    return c


async def _created(response: httpx.Response) -> dict[str, Any]:
    assert response.status_code == 201, response.text
    body: dict[str, Any] = response.json()
    return body


async def _product_with_a_device(client: httpx.AsyncClient) -> dict[str, Any]:
    product = await _created(
        await client.post(f"{API_WEB}/products/", json={"product_number": "M26001"})
    )
    medium = await _created(
        await client.post(
            f"{RESOURCES}/options",
            json={"category": "driving_medium", "label": {"enGB": "Pneumatics"}, "letter": "P"},
        )
    )
    kind = await _created(
        await client.post(
            f"{RESOURCES}/kinds",
            json={
                "label": {"enGB": "Linear drive"},
                "positions": [{"label": {"enGB": "Retracted"}}, {"label": {"enGB": "Extended"}}],
            },
        )
    )
    await _created(
        await client.post(
            f"{API_WEB}/products/{product['id']}/devices",
            json={
                "location": "B01-W4-L",
                "name": "Lift cylinder",
                "driving_medium_id": medium["id"],
                "kind_id": kind["id"],
            },
        )
    )
    return product


def _text(result: dict[str, Any]) -> str:
    return str(result["content"][0]["text"])


async def test_project_status_answers_by_number_with_live_work_and_summary(
    client: httpx.AsyncClient, manager: httpx.AsyncClient, token: str
) -> None:
    await _created(
        await manager.post(
            f"{API_WEB}/projects/", json={"project_number": "J-100", "description": "Press line"}
        )
    )

    result = await call_tool(client, token, "project_status", {"project_number": "J-100"})

    assert result["isError"] is False, _text(result)
    data = result["structuredContent"]
    assert data["project"]["project_number"] == "J-100"
    assert data["project"]["live_work"] is not None
    assert "changes" not in data["project"]
    assert data["summary"]["order_count"] == 0
    # Order costs stay out while the agent settings leave costs out.
    assert "total_ordered_cost" not in data["summary"]


async def test_project_status_names_an_unknown_number(
    client: httpx.AsyncClient, token: str
) -> None:
    result = await call_tool(client, token, "project_status", {"project_number": "J-404"})

    assert result["isError"] is True
    assert "J-404" in _text(result)


async def test_product_status_lists_the_device_completeness(
    client: httpx.AsyncClient, manager: httpx.AsyncClient, token: str
) -> None:
    await _product_with_a_device(manager)

    result = await call_tool(client, token, "product_status", {"product_number": "M26001"})

    assert result["isError"] is False, _text(result)
    data = result["structuredContent"]
    assert data["product"]["product_number"] == "M26001"
    assert data["device_count"] == 1
    [device] = data["devices"]
    assert "Lift cylinder" in device["device_name"]
    assert device["sequence_coverage"] == "none"
    assert device["plans_checked"] == []


async def test_renumber_impact_shows_the_new_device_names(
    client: httpx.AsyncClient, manager: httpx.AsyncClient, token: str
) -> None:
    await _product_with_a_device(manager)

    result = await call_tool(
        client, token, "renumber_impact", {"product_number": "M26001", "new_number": "M26999"}
    )

    assert result["isError"] is False, _text(result)
    data = result["structuredContent"]
    assert data["device_count"] == 1
    [example] = data["device_examples"]
    assert "M26999" in example["new_name"]
    assert data["released_document_count"] == 0


async def test_product_devices_names_positions_and_what_is_missing(
    client: httpx.AsyncClient, manager: httpx.AsyncClient, token: str
) -> None:
    product = await _created(
        await manager.post(
            f"{API_WEB}/products/",
            json={"product_number": "M26002", "contains_electrics": True},
        )
    )
    kind = await _created(
        await manager.post(
            f"{RESOURCES}/kinds",
            json={
                "label": {"enGB": "Gripper"},
                "positions": [{"label": {"enGB": "Open"}}, {"label": {"enGB": "Closed"}}],
                "without_driving_medium": True,
            },
        )
    )
    opened, closed = (p["id"] for p in kind["positions"])
    drawn = await _created(
        await manager.post(
            f"{API_WEB}/products/{product['id']}/devices",
            json={
                "name": "Gripper left",
                "kind_id": kind["id"],
                "initial_position_id": opened,
                "position_labels": {str(closed): "Part held"},
                "travel_times_ms": {str(closed): 300},
            },
        )
    )
    await _created(
        await manager.post(
            f"{API_WEB}/products/{product['id']}/devices",
            json={"name": "Gripper right", "kind_id": kind["id"]},
        )
    )
    for plan in ("cad_assembly", "eplan"):
        ticked = await manager.put(
            f"{API_WEB}/product-devices/{drawn['id']}/checks/{plan}", json={"checked": True}
        )
        assert ticked.status_code == 204, ticked.text

    result = await call_tool(client, token, "product_devices", {"product_number": "M26002"})

    assert result["isError"] is False, _text(result)
    data = result["structuredContent"]
    assert data["plans_required"] == ["cad_assembly", "eplan"]
    assert data["device_count"] == 2
    left = next(d for d in data["devices"] if "Gripper left" in d["name"])
    assert left["kind"] == "Gripper"
    assert left["initial_position"] == "Open"
    assert [(p["position"], p["travel_time_ms"]) for p in left["positions"]] == [
        ("Open", None),
        ("Part held", 300),
    ]
    assert left["plans_missing"] == []
    assert left["sequence_coverage"] == "none"
    assert {c["plan"] for c in left["plans_checked"]} == {"cad_assembly", "eplan"}
    # Who ticked a plan stays out while the agent settings leave names out.
    assert {c["checked_by_name"] for c in left["plans_checked"]} == {"[hidden]"}

    incomplete = await call_tool(
        client,
        token,
        "product_devices",
        {"product_number": "M26002", "only_incomplete": True, "search": "right"},
    )

    assert incomplete["isError"] is False, _text(incomplete)
    [right] = incomplete["structuredContent"]["devices"]
    assert "Gripper right" in right["name"]
    assert right["plans_missing"] == ["cad_assembly", "eplan"]


async def test_product_devices_names_an_unknown_product(
    client: httpx.AsyncClient, token: str
) -> None:
    result = await call_tool(client, token, "product_devices", {"product_number": "M404"})

    assert result["isError"] is True
    assert "M404" in _text(result)
