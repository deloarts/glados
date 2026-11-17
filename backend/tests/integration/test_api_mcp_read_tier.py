"""
HTTP-level coverage of the read tier's agent tools and prompts on the MCP
surface: the global search, the lifecycle explanation, and the prompts a
client lists and fetches. Products are seeded through the real repository
and every call goes through the protocol the way an agent client sends it.
"""

from collections.abc import Awaitable
from collections.abc import Callable
from datetime import UTC
from datetime import datetime

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.value_objects.permission import Permission
from src.modules.workspace.adapters.outbound.persistence.repositories.product_repository import (
    SqlAlchemyProductRepository,
)
from src.modules.workspace.domain.entities.product import Product
from src.read.domain.services.state_machine_catalog import build_state_machine_catalog
from tests.integration._mcp_helpers import call_tool
from tests.integration._mcp_helpers import mint_agent_token
from tests.integration._mcp_helpers import rpc
from tests.integration._mcp_helpers import save_agent_settings

PROMPTS = {"morning-briefing", "project-report", "why-late", "procurement-review", "weekly-kpis"}


@pytest.fixture
async def agents_on(db: AsyncSession) -> None:
    await save_agent_settings(db)


@pytest.fixture
async def agent_owner(create_user: Callable[..., Awaitable[User]]) -> User:
    return await create_user(
        username="read-planner",
        email="read-planner@example.com",
        permissions=[Permission.WRITE_PAT, Permission.USE_MCP],
    )


@pytest.fixture
def mint(db: AsyncSession, agent_owner: User) -> Callable[..., Awaitable[str]]:
    async def _mint(permissions: list[str], expires_in_days: int | None = 7) -> str:
        return await mint_agent_token(db, agent_owner, permissions, expires_in_days=expires_in_days)

    return _mint


async def _product(db: AsyncSession, creator_id: int, number: str) -> int:
    product = await SqlAlchemyProductRepository(db).save(
        Product(id=0, created=datetime.now(UTC), creator_id=creator_id, product_number=number)
    )
    await db.commit()
    return product.id


# ── search ────────────────────────────────────────────────────────────


@pytest.mark.usefixtures("agents_on")
async def test_search_finds_a_product_and_leaves_out_kinds_without_hits(
    client: httpx.AsyncClient,
    db: AsyncSession,
    agent_owner: User,
    mint: Callable[..., Awaitable[str]],
) -> None:
    product_id = await _product(db, agent_owner.id, "PR-MCP-SEARCH")
    token = await mint([Permission.USE_MCP])

    result = await call_tool(client, token, "search", {"query": "PR-MCP-SEARCH"})

    assert result["isError"] is False, result
    data = result["structuredContent"]
    assert data["query"] == "PR-MCP-SEARCH"
    [group] = data["groups"]
    assert group["resource"] == "products"
    assert [hit["id"] for hit in group["items"]] == [product_id]


@pytest.mark.usefixtures("agents_on")
async def test_search_keeps_only_the_kinds_asked_for(
    client: httpx.AsyncClient,
    db: AsyncSession,
    agent_owner: User,
    mint: Callable[..., Awaitable[str]],
) -> None:
    await _product(db, agent_owner.id, "PR-MCP-ONLY")
    token = await mint([Permission.USE_MCP])

    result = await call_tool(
        client, token, "search", {"query": "PR-MCP-ONLY", "resources": ["projects"]}
    )

    assert result["isError"] is False, result
    assert result["structuredContent"]["groups"] == []


# ── explain_lifecycle ─────────────────────────────────────────────────


@pytest.mark.usefixtures("agents_on")
async def test_explain_lifecycle_without_a_name_lists_the_lifecycles(
    client: httpx.AsyncClient, mint: Callable[..., Awaitable[str]]
) -> None:
    token = await mint([Permission.USE_MCP])

    result = await call_tool(client, token, "explain_lifecycle")

    assert result["isError"] is False, result
    lifecycles = result["structuredContent"]["lifecycles"]
    assert [m["key"] for m in lifecycles] == [g.key for g in build_state_machine_catalog()]
    assert "states" not in lifecycles[0]


@pytest.mark.usefixtures("agents_on")
async def test_explain_lifecycle_answers_one_lifecycle_by_key_or_entity(
    client: httpx.AsyncClient, mint: Callable[..., Awaitable[str]]
) -> None:
    token = await mint([Permission.USE_MCP])

    by_key = await call_tool(client, token, "explain_lifecycle", {"name": "lot_status"})
    by_entity = await call_tool(client, token, "explain_lifecycle", {"name": "lot"})
    unknown = await call_tool(client, token, "explain_lifecycle", {"name": "no_such_machine"})

    assert by_key["isError"] is False, by_key
    assert by_key["structuredContent"]["key"] == "lot_status"
    assert by_key["structuredContent"]["states"]
    assert by_entity["structuredContent"] == by_key["structuredContent"]
    assert unknown["isError"] is True
    assert "lot_status" in unknown["content"][0]["text"]


# ── Prompts ───────────────────────────────────────────────────────────


@pytest.mark.usefixtures("agents_on")
async def test_prompts_list_names_every_prompt_with_its_arguments(
    client: httpx.AsyncClient, mint: Callable[..., Awaitable[str]]
) -> None:
    token = await mint([Permission.USE_MCP])

    response = await rpc(client, token, "prompts/list")

    assert response.status_code == 200, response.text
    prompts = {p["name"]: p for p in response.json()["result"]["prompts"]}
    assert set(prompts) >= PROMPTS
    assert prompts["why-late"]["arguments"] == [
        {"name": "lot_number", "description": "The number of the production lot.", "required": True}
    ]
    assert prompts["procurement-review"]["arguments"][0]["required"] is False
    assert not prompts["morning-briefing"].get("arguments")


@pytest.mark.usefixtures("agents_on")
async def test_prompts_get_renders_the_argument_into_the_instruction(
    client: httpx.AsyncClient, mint: Callable[..., Awaitable[str]]
) -> None:
    token = await mint([Permission.USE_MCP])

    response = await rpc(
        client,
        token,
        "prompts/get",
        {"name": "project-report", "arguments": {"project_number": "P-24017"}},
    )

    assert response.status_code == 200, response.text
    [message] = response.json()["result"]["messages"]
    assert message["role"] == "user"
    text = message["content"]["text"]
    assert "P-24017" in text
    assert "project_status" in text
    assert "commit it in the Glados web app" in text


@pytest.mark.usefixtures("agents_on")
async def test_procurement_review_offers_drafts_and_works_without_a_project(
    client: httpx.AsyncClient, mint: Callable[..., Awaitable[str]]
) -> None:
    token = await mint([Permission.USE_MCP])

    response = await rpc(client, token, "prompts/get", {"name": "procurement-review"})

    assert response.status_code == 200, response.text
    text = response.json()["result"]["messages"][0]["content"]["text"]
    assert "every open project" in text
    assert "draft_purchase_order" in text
    assert "never create a draft I did not ask for" in text


@pytest.mark.usefixtures("agents_on")
async def test_prompts_get_without_a_required_argument_is_a_protocol_error(
    client: httpx.AsyncClient, mint: Callable[..., Awaitable[str]]
) -> None:
    token = await mint([Permission.USE_MCP])

    response = await rpc(client, token, "prompts/get", {"name": "why-late"})

    assert response.status_code == 200, response.text
    body = response.json()
    assert "result" not in body
    assert body["error"]["code"] == -32602
    assert "lot_number" in body["error"]["message"]
