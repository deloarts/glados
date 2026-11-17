"""
The care of agent access around the MCP surface: API keys reach the read
tools only, the hourly sweep revokes idle agent tokens and warns about
expiring ones, and the agent call log and agent settings are read and
changed through the web API with the right permissions.
"""

from collections.abc import Awaitable
from collections.abc import Callable
from datetime import timedelta

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.bootstrap.adapters.outbound.persistence.repositories.admin_settings_repository import (
    SqlAlchemyAdminSettingsRepository,
)
from src.modules.platform.adapters.outbound.persistence.models.notification_model import (
    NotificationOrmModel,
)
from src.modules.platform.adapters.outbound.persistence.models.security_event_model import (
    SecurityEventOrmModel,
)
from src.modules.platform.adapters.outbound.persistence.repositories.agent_call_repository import (
    SqlAlchemyAgentCallRepository,
)
from src.modules.platform.adapters.outbound.persistence.repositories.api_key_repository import (
    SqlAlchemyApiKeyRepository,
)
from src.modules.platform.adapters.outbound.persistence.repositories.notification_repository import (
    SqlAlchemyNotificationRepository,
)
from src.modules.platform.adapters.outbound.persistence.repositories.pat_repository import (
    SqlAlchemyPatRepository,
)
from src.modules.platform.adapters.outbound.persistence.repositories.security_event_repository import (
    SqlAlchemySecurityEventRepository,
)
from src.modules.platform.adapters.outbound.persistence.repositories.user_repository import (
    SqlAlchemyUserRepository,
)
from src.modules.platform.adapters.outbound.persistence.unit_of_work import SqlAlchemyUnitOfWork
from src.modules.platform.application.dto.api_key_dto import CreateApiKeyCommand
from src.modules.platform.application.services.security_audit import SecurityAudit
from src.modules.platform.application.use_cases.agent.sweep_agent_tokens import SweepAgentTokens
from src.modules.platform.application.use_cases.api_key.create_api_key import CreateApiKey
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.value_objects.permission import Permission
from src.modules.platform.infrastructure.security.hashing import aget_hash
from src.modules.platform.ports.outbound.repositories.agent_call_repository import (
    AgentCallFilterDto,
)
from src.modules.platform.ports.outbound.repositories.api_key_repository import ApiKeyFilterDto
from src.modules.platform.ports.outbound.repositories.pat_repository import PatFilterDto
from src.shared_kernel.domain.services.clock import now_utc
from tests.integration._mcp_helpers import call_tool
from tests.integration._mcp_helpers import list_tool_names
from tests.integration._mcp_helpers import mint_agent_token
from tests.integration._mcp_helpers import rpc
from tests.integration._mcp_helpers import save_agent_settings
from tests.integration._mcp_helpers import seed_security

pytestmark = pytest.mark.usefixtures("agents_on")


@pytest.fixture
async def agents_on(db: AsyncSession) -> None:
    await save_agent_settings(db)
    await seed_security(db, enable_api_key_auth=True)


@pytest.fixture
async def owner(create_user: Callable[..., Awaitable[User]]) -> User:
    return await create_user(
        username="planner",
        email="planner@example.com",
        permissions=[
            Permission.WRITE_PAT,
            Permission.USE_MCP,
            Permission.WRITE_ORDERS,
            Permission.WRITE_LOTS,
            Permission.MANAGE_API_KEYS,
        ],
    )


async def _mint_api_key(db: AsyncSession, owner: User, permissions: list[str]) -> str:
    result = await CreateApiKey(
        SqlAlchemyApiKeyRepository(db),
        SqlAlchemyUserRepository(db),
        SqlAlchemyUnitOfWork(db),
        settings_repo=SqlAlchemyAdminSettingsRepository(db),
        hash_password_fn=aget_hash,
    ).execute(
        actor=owner,
        cmd=CreateApiKeyCommand(name="nightly", permissions=permissions, expires_in_days=30),
    )
    return result.key


def _sweep(db: AsyncSession) -> SweepAgentTokens:
    return SweepAgentTokens(
        SqlAlchemyAdminSettingsRepository(db),
        SqlAlchemyPatRepository(db),
        SqlAlchemyApiKeyRepository(db),
        SqlAlchemyUserRepository(db),
        SqlAlchemyAgentCallRepository(db),
        SqlAlchemyNotificationRepository(db),
        uow=SqlAlchemyUnitOfWork(db),
        audit=SecurityAudit(SqlAlchemySecurityEventRepository(db)),
    )


# ── API keys ──────────────────────────────────────────────────────────


async def test_api_key_agent_sees_read_tools_but_no_draft_tool(
    client: httpx.AsyncClient, db: AsyncSession, owner: User
) -> None:
    key = await _mint_api_key(db, owner, [Permission.USE_MCP, Permission.WRITE_ORDERS])
    pat = await mint_agent_token(db, owner, [Permission.USE_MCP, Permission.WRITE_ORDERS])

    key_tools = await list_tool_names(client, key)
    pat_tools = await list_tool_names(client, pat)

    assert "my_notifications" in key_tools
    drafts = {name for name in pat_tools if name.startswith("draft_")}
    assert drafts.isdisjoint(key_tools)


async def test_api_key_agent_is_refused_while_api_key_auth_is_off(
    client: httpx.AsyncClient, db: AsyncSession, owner: User
) -> None:
    key = await _mint_api_key(db, owner, [Permission.USE_MCP])
    await seed_security(db, enable_api_key_auth=False)

    response = await rpc(client, key, "tools/list")

    assert response.status_code == 403


async def test_api_key_agent_calls_are_logged_against_the_key(
    client: httpx.AsyncClient, db: AsyncSession, owner: User
) -> None:
    key = await _mint_api_key(db, owner, [Permission.USE_MCP])

    await call_tool(client, key, "my_notifications")

    [call] = (await SqlAlchemyAgentCallRepository(db).get_page(AgentCallFilterDto()))[1]
    assert (call.token_kind.value, call.token_name, call.pat_id) == ("api_key", "nightly", None)


# ── The sweep ─────────────────────────────────────────────────────────


async def test_sweep_revokes_an_unused_agent_pat_and_tells_its_owner(
    db: AsyncSession, owner: User
) -> None:
    await mint_agent_token(db, owner, [Permission.USE_MCP], expires_in_days=30)

    result = await _sweep(db).execute(now=now_utc() + timedelta(days=15))

    assert result.revoked == 1
    db.expire_all()
    [pat] = (
        await SqlAlchemyPatRepository(db).get_multi_for_user(
            owner.id, PatFilterDto(include_revoked=True)
        )
    )[1]
    assert pat.revoked_at is not None
    event = (await db.execute(select(SecurityEventOrmModel))).scalars().all()[-1]
    assert event.event_type == "pat_revoked"
    assert event.detail["reason"] == "idle"
    notice = (await db.execute(select(NotificationOrmModel))).scalars().one()
    assert notice.type == "agent_token_revoked"


async def test_sweep_keeps_a_recently_used_token(
    client: httpx.AsyncClient, db: AsyncSession, owner: User
) -> None:
    token = await mint_agent_token(db, owner, [Permission.USE_MCP], expires_in_days=30)
    await call_tool(client, token, "my_notifications")

    result = await _sweep(db).execute(now=now_utc() + timedelta(days=13))

    assert result.revoked == 0


async def test_sweep_leaves_a_token_without_use_mcp_alone(db: AsyncSession, owner: User) -> None:
    await mint_agent_token(db, owner, [Permission.WRITE_ORDERS], expires_in_days=30)

    result = await _sweep(db).execute(now=now_utc() + timedelta(days=29))

    assert (result.revoked, result.warned) == (0, 0)


async def test_sweep_warns_once_about_an_expiring_agent_token(
    client: httpx.AsyncClient, db: AsyncSession, owner: User
) -> None:
    token = await mint_agent_token(db, owner, [Permission.USE_MCP], expires_in_days=2)
    await call_tool(client, token, "my_notifications")

    first = await _sweep(db).execute()
    second = await _sweep(db).execute()

    assert (first.warned, second.warned) == (1, 0)


async def test_sweep_revokes_an_idle_agent_api_key_and_its_service_account(
    db: AsyncSession, owner: User
) -> None:
    await _mint_api_key(db, owner, [Permission.USE_MCP])

    result = await _sweep(db).execute(now=now_utc() + timedelta(days=15))

    assert result.revoked == 1
    db.expire_all()
    [key] = (await SqlAlchemyApiKeyRepository(db).get_multi(ApiKeyFilterDto(include_revoked=True)))[
        1
    ]
    assert key.revoked_at is not None
    service_user = await SqlAlchemyUserRepository(db).get_by_id(key.user_id)
    assert service_user is not None and not service_user.is_active


# ── The web API ───────────────────────────────────────────────────────


async def test_agent_call_log_shows_a_user_only_their_own_calls(
    client: httpx.AsyncClient,
    db: AsyncSession,
    owner: User,
    auth_client: Callable[..., Awaitable[httpx.AsyncClient]],
) -> None:
    token = await mint_agent_token(db, owner, [Permission.USE_MCP])
    await call_tool(client, token, "my_notifications")

    stranger = await auth_client(username="stranger", email="stranger@example.com")
    admin = await auth_client(
        [Permission.READ_SETTINGS], username="admin", email="admin@example.com"
    )

    own = await stranger.get("/api/v1/web/agent-calls/")
    every = await admin.get("/api/v1/web/agent-calls/", params={"tool": "my_notifications"})

    assert own.status_code == 200 and own.json()["total"] == 0
    assert every.json()["total"] == 1
    assert every.json()["items"][0]["token_name"] == "agent"


async def test_agent_call_log_filters_by_user_for_admins_only(
    client: httpx.AsyncClient,
    db: AsyncSession,
    owner: User,
    auth_client: Callable[..., Awaitable[httpx.AsyncClient]],
) -> None:
    token = await mint_agent_token(db, owner, [Permission.USE_MCP])
    await call_tool(client, token, "my_notifications")

    stranger = await auth_client(username="stranger", email="stranger@example.com")
    admin = await auth_client(
        [Permission.READ_SETTINGS], username="admin", email="admin@example.com"
    )

    snooped = await stranger.get("/api/v1/web/agent-calls/", params={"user_id": owner.id})
    owners = await admin.get("/api/v1/web/agent-calls/", params={"user_id": owner.id})
    nobodys = await admin.get("/api/v1/web/agent-calls/", params={"user_id": owner.id + 999})

    assert snooped.json()["total"] == 0
    assert owners.json()["total"] == 1
    assert owners.json()["items"][0]["user_id"] == owner.id
    assert nobodys.json()["total"] == 0


async def test_agent_settings_need_read_and_write_settings(
    auth_client: Callable[..., Awaitable[httpx.AsyncClient]],
) -> None:
    reader = await auth_client([Permission.READ_SETTINGS])
    writer = await auth_client(
        [Permission.READ_SETTINGS, Permission.WRITE_SETTINGS],
        username="writer",
        email="writer@example.com",
    )

    read = await reader.get("/api/v1/web/admin/settings/agents")
    refused = await reader.put("/api/v1/web/admin/settings/agents", json={"enabled": False})
    written = await writer.put(
        "/api/v1/web/admin/settings/agents",
        json={
            "enabled": True,
            "processing_approved": True,
            "approved_providers": "Test provider",
            "allowed_origins": ["https://Glados.example.com/"],
        },
        headers={"X-Requested-With": "glados"},
    )

    assert read.status_code == 200 and read.json()["enabled"] is True
    assert refused.status_code == 403
    assert written.status_code == 200
    assert written.json()["allowed_origins"] == ["https://glados.example.com"]
    assert written.json()["include_person_names"] is False


async def test_agent_settings_refuse_an_origin_with_a_path(
    auth_client: Callable[..., Awaitable[httpx.AsyncClient]],
) -> None:
    writer = await auth_client([Permission.READ_SETTINGS, Permission.WRITE_SETTINGS])

    response = await writer.put(
        "/api/v1/web/admin/settings/agents",
        json={"allowed_origins": ["https://glados.example.com/app"]},
        headers={"X-Requested-With": "glados"},
    )

    assert response.status_code == 422
