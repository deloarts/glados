"""
Shared helpers of the MCP surface tests: switching agent access on with the
company's approval recorded, minting an agent token through the real
CreatePat use case with its owner's consent, and calling a tool over HTTP
the way an agent client does.
"""

from datetime import UTC
from datetime import datetime
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.bootstrap.adapters.outbound.persistence.admin_settings_seed import ADMIN_SETTINGS_SEEDS
from src.bootstrap.adapters.outbound.persistence.repositories.admin_settings_repository import (
    SqlAlchemyAdminSettingsRepository,
)
from src.modules.platform.adapters.outbound.persistence.models.agent_call_model import (
    AgentCallOrmModel,
)
from src.modules.platform.adapters.outbound.persistence.repositories.agent_consent_repository import (
    SqlAlchemyAgentConsentRepository,
)
from src.modules.platform.adapters.outbound.persistence.repositories.pat_repository import (
    SqlAlchemyPatRepository,
)
from src.modules.platform.adapters.outbound.persistence.unit_of_work import SqlAlchemyUnitOfWork
from src.modules.platform.application.dto.pat_dto import CreatePatCommand
from src.modules.platform.application.use_cases.pat.create_pat import CreatePat
from src.modules.platform.domain.entities.admin_settings.agents import AdminAgentSettings
from src.modules.platform.domain.entities.agent_consent import AgentConsent
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.services.agent_policy import AGENT_CONSENT_VERSION
from src.shared_kernel.domain.services.clock import now_utc

# Before every consent a test gives, so a consent counts unless a test
# moves the approval past it.
APPROVED_AT = datetime(2020, 1, 1, tzinfo=UTC)

MCP = "/api/v1/mcp"
_ACCEPT = {"Accept": "application/json, text/event-stream"}


async def seed_security(db: AsyncSession, **fields: Any) -> None:
    """The security settings, which the integration schema does not seed."""
    seed = next(s for s in ADMIN_SETTINGS_SEEDS if s.label == "security")
    settings = seed.build()
    for name, value in fields.items():
        setattr(settings, name, value)
    await SqlAlchemyAdminSettingsRepository(db).save_security(settings)
    await db.commit()


async def save_agent_settings(db: AsyncSession, **fields: Any) -> None:
    """Agent access approved and switched on, with any field overridden."""
    defaults: dict[str, Any] = {
        "enabled": True,
        "approved_providers": "Test provider",
        "processing_approved_at": APPROVED_AT,
    }
    await SqlAlchemyAdminSettingsRepository(db).save_agents(
        AdminAgentSettings(id=1, **{**defaults, **fields})
    )
    await db.commit()


async def give_agent_consent(db: AsyncSession, user: User, *, version: int | None = None) -> None:
    """The user's agent consent, given now."""
    await SqlAlchemyAgentConsentRepository(db).save(
        AgentConsent(
            id=0,
            user_id=user.id,
            consent_version=AGENT_CONSENT_VERSION if version is None else version,
            consented_at=now_utc(),
        )
    )
    await db.commit()


async def mint_agent_token(
    db: AsyncSession,
    owner: User,
    permissions: list[str],
    *,
    expires_in_days: int | None = 7,
    name: str = "agent",
    consent: bool = True,
) -> str:
    """A real PAT of `owner`, who must hold write:pat and every permission
    granted, the raw token returned. The owner gives the agent consent
    unless `consent` is false."""
    result = await CreatePat(
        SqlAlchemyPatRepository(db),
        settings_repo=SqlAlchemyAdminSettingsRepository(db),
        uow=SqlAlchemyUnitOfWork(db),
    ).execute(
        actor=owner,
        cmd=CreatePatCommand(name=name, permissions=permissions, expires_in_days=expires_in_days),
    )
    if consent:
        await give_agent_consent(db, owner)
    return result.token


async def rpc(
    client: httpx.AsyncClient,
    token: str | None,
    method: str,
    params: dict[str, Any] | None = None,
    **headers: str,
) -> httpx.Response:
    """One JSON-RPC message to the MCP surface."""
    sent = {**_ACCEPT, **headers}
    if token is not None:
        sent["Authorization"] = f"Bearer {token}"
    body: dict[str, Any] = {"jsonrpc": "2.0", "id": 1, "method": method}
    if params is not None:
        body["params"] = params
    return await client.post(MCP, json=body, headers=sent)


async def call_tool(
    client: httpx.AsyncClient, token: str, tool: str, arguments: dict[str, Any] | None = None
) -> dict[str, Any]:
    """The `result` of a tools/call: `isError`, `content` and, on success,
    `structuredContent` (a dict, or `{"items": [...]}` for a list)."""
    response = await rpc(client, token, "tools/call", {"name": tool, "arguments": arguments or {}})
    assert response.status_code == 200, response.text
    result: dict[str, Any] = response.json()["result"]
    return result


async def list_tool_names(client: httpx.AsyncClient, token: str) -> list[str]:
    response = await rpc(client, token, "tools/list")
    assert response.status_code == 200, response.text
    return [t["name"] for t in response.json()["result"]["tools"]]


async def logged_calls(db: AsyncSession) -> list[AgentCallOrmModel]:
    """Every agent call log row, oldest first."""
    db.expire_all()
    return list(
        (await db.execute(select(AgentCallOrmModel).order_by(AgentCallOrmModel.id))).scalars()
    )
