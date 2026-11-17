"""
HTTP-level coverage of the MCP surface (`/api/v1/mcp`): who gets in, what a
token sees, and what every tool call leaves in the agent call log. Tokens
are minted through the real CreatePat use case.
"""

from collections.abc import Awaitable
from collections.abc import Callable
from datetime import timedelta

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.platform.adapters.outbound.persistence.repositories.pat_repository import (
    SqlAlchemyPatRepository,
)
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.exceptions import TokenExpiryRequiredError
from src.modules.platform.domain.exceptions import TokenLifetimeExceededError
from src.modules.platform.domain.value_objects.permission import Permission
from src.shared_kernel.domain.services.clock import now_utc
from tests.integration._mcp_helpers import call_tool
from tests.integration._mcp_helpers import logged_calls
from tests.integration._mcp_helpers import mint_agent_token
from tests.integration._mcp_helpers import rpc
from tests.integration._mcp_helpers import save_agent_settings
from tests.integration._mcp_helpers import seed_security


@pytest.fixture
async def agents_on(db: AsyncSession) -> None:
    await save_agent_settings(db)


@pytest.fixture
async def agent_owner(create_user: Callable[..., Awaitable[User]]) -> User:
    return await create_user(
        username="planner",
        email="planner@example.com",
        permissions=[Permission.WRITE_PAT, Permission.USE_MCP, Permission.WRITE_ORDERS],
    )


@pytest.fixture
def mint(db: AsyncSession, agent_owner: User) -> Callable[..., Awaitable[str]]:
    async def _mint(permissions: list[str], expires_in_days: int | None = 7) -> str:
        return await mint_agent_token(db, agent_owner, permissions, expires_in_days=expires_in_days)

    return _mint


# ── Getting in ────────────────────────────────────────────────────────


async def test_mcp_refuses_everyone_while_switched_off(
    client: httpx.AsyncClient, db: AsyncSession, mint: Callable[..., Awaitable[str]]
) -> None:
    await save_agent_settings(db, enabled=False)
    token = await mint([Permission.USE_MCP])

    response = await rpc(client, token, "tools/list")

    assert response.status_code == 403
    assert response.json()["code"] == "AgentAccessDisabledError"


@pytest.mark.usefixtures("agents_on")
async def test_mcp_without_bearer_answers_401_with_a_challenge(
    client: httpx.AsyncClient,
) -> None:
    response = await rpc(client, None, "tools/list")

    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"].startswith("Bearer")


@pytest.mark.usefixtures("agents_on")
async def test_mcp_refuses_a_pat_without_use_mcp(
    client: httpx.AsyncClient, mint: Callable[..., Awaitable[str]]
) -> None:
    token = await mint([Permission.WRITE_ORDERS], expires_in_days=None)

    response = await rpc(client, token, "tools/list")

    assert response.status_code == 403
    assert response.json()["code"] == "AgentTokenNotAllowedError"


@pytest.mark.usefixtures("agents_on")
async def test_mcp_refuses_the_token_in_the_api_key_header(
    client: httpx.AsyncClient, mint: Callable[..., Awaitable[str]]
) -> None:
    token = await mint([Permission.USE_MCP])

    response = await rpc(client, None, "tools/list", **{"X-Api-Key": token})

    assert response.status_code == 401


@pytest.mark.usefixtures("agents_on")
async def test_mcp_refuses_a_browser_origin_outside_the_allowlist(
    client: httpx.AsyncClient, mint: Callable[..., Awaitable[str]]
) -> None:
    token = await mint([Permission.USE_MCP])

    response = await rpc(client, token, "tools/list", Origin="https://evil.example.com")

    assert response.status_code == 403
    assert response.json()["code"] == "AgentOriginRefusedError"


async def test_mcp_lets_an_allowlisted_origin_in(
    client: httpx.AsyncClient, db: AsyncSession, mint: Callable[..., Awaitable[str]]
) -> None:
    await save_agent_settings(db, allowed_origins=["https://glados.example.com"])
    token = await mint([Permission.USE_MCP])

    response = await rpc(client, token, "tools/list", Origin="https://glados.example.com")

    assert response.status_code == 200


@pytest.mark.usefixtures("agents_on")
async def test_mcp_refuses_a_revoked_token_on_the_next_call(
    client: httpx.AsyncClient, db: AsyncSession, mint: Callable[..., Awaitable[str]]
) -> None:
    token = await mint([Permission.USE_MCP])
    assert (await rpc(client, token, "tools/list")).status_code == 200

    repo = SqlAlchemyPatRepository(db)
    [pat] = await repo.list_unrevoked_unexpired()
    pat.revoked_at = now_utc()
    await repo.save(pat)
    await db.commit()

    assert (await rpc(client, token, "tools/list")).status_code == 401


# ── Token lifetime ────────────────────────────────────────────────────


@pytest.mark.usefixtures("agents_on")
async def test_agent_token_needs_an_expiry_even_without_a_general_cap(
    db: AsyncSession, mint: Callable[..., Awaitable[str]]
) -> None:
    await seed_security(db, token_max_lifetime_days=0)

    with pytest.raises(TokenExpiryRequiredError):
        await mint([Permission.USE_MCP], expires_in_days=None)
    with pytest.raises(TokenLifetimeExceededError):
        await mint([Permission.USE_MCP], expires_in_days=31)
    assert await mint([Permission.USE_MCP], expires_in_days=30)


# ── The protocol ──────────────────────────────────────────────────────


@pytest.mark.usefixtures("agents_on")
async def test_mcp_initialize_names_glados_and_its_instructions(
    client: httpx.AsyncClient, mint: Callable[..., Awaitable[str]]
) -> None:
    token = await mint([Permission.USE_MCP])

    response = await rpc(
        client,
        token,
        "initialize",
        {
            "protocolVersion": "2025-06-18",
            "capabilities": {},
            "clientInfo": {"name": "pytest", "version": "1"},
        },
    )

    result = response.json()["result"]
    assert result["serverInfo"]["name"] == "glados"
    assert "draft" in result["instructions"]


@pytest.mark.usefixtures("agents_on")
async def test_mcp_tool_call_is_logged_with_its_token(
    client: httpx.AsyncClient, db: AsyncSession, mint: Callable[..., Awaitable[str]]
) -> None:
    token = await mint([Permission.USE_MCP])

    result = await call_tool(client, token, "my_notifications", {"limit": 5})

    assert result["isError"] is False
    assert result["structuredContent"]["items"] == []
    [call] = await logged_calls(db)
    assert (call.tool, call.outcome, call.token_name) == ("my_notifications", "ok", "agent")
    assert call.arguments == {"limit": 5}


@pytest.mark.usefixtures("agents_on")
async def test_mcp_unknown_argument_is_an_error_the_agent_reads(
    client: httpx.AsyncClient, db: AsyncSession, mint: Callable[..., Awaitable[str]]
) -> None:
    token = await mint([Permission.USE_MCP])

    result = await call_tool(client, token, "my_notifications", {"unread": True})

    assert result["isError"] is True
    assert "Invalid arguments" in result["content"][0]["text"]
    [call] = await logged_calls(db)
    assert call.outcome == "error"


@pytest.mark.usefixtures("agents_on")
async def test_mcp_unknown_tool_is_refused_and_logged(
    client: httpx.AsyncClient, db: AsyncSession, mint: Callable[..., Awaitable[str]]
) -> None:
    token = await mint([Permission.USE_MCP])

    result = await call_tool(client, token, "drop_all_tables")

    assert result["isError"] is True
    [call] = await logged_calls(db)
    assert (call.tool, call.outcome) == ("drop_all_tables", "refused")


async def test_mcp_call_budget_refuses_the_call_after_the_last(
    client: httpx.AsyncClient, db: AsyncSession, mint: Callable[..., Awaitable[str]]
) -> None:
    await save_agent_settings(db, calls_per_minute=2)
    token = await mint([Permission.USE_MCP])

    first = await call_tool(client, token, "my_notifications")
    second = await call_tool(client, token, "my_notifications")
    third = await call_tool(client, token, "my_notifications")

    assert not first["isError"] and not second["isError"]
    assert third["isError"] is True
    assert "calls in the last minute" in third["content"][0]["text"]


@pytest.mark.usefixtures("agents_on")
async def test_mcp_call_log_keeps_the_call_time(
    client: httpx.AsyncClient, db: AsyncSession, mint: Callable[..., Awaitable[str]]
) -> None:
    token = await mint([Permission.USE_MCP])
    before = now_utc() - timedelta(seconds=1)

    await call_tool(client, token, "my_notifications")

    [call] = await logged_calls(db)
    assert call.called_at.replace(tzinfo=before.tzinfo) >= before
