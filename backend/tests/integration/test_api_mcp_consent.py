"""
The two confirmations agent access needs: the company's approval of AI
processing in the agent settings, without which agent access cannot be
switched on, and every user's own consent, without which their agent
tokens are refused. Changing what users consented to asks them again, and
withdrawing revokes the user's agent tokens.
"""

from collections.abc import Awaitable
from collections.abc import Callable
from datetime import timedelta

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.bootstrap.adapters.outbound.persistence.repositories.admin_settings_repository import (
    SqlAlchemyAdminSettingsRepository,
)
from src.modules.platform.adapters.outbound.persistence.repositories.api_key_repository import (
    SqlAlchemyApiKeyRepository,
)
from src.modules.platform.adapters.outbound.persistence.repositories.pat_repository import (
    SqlAlchemyPatRepository,
)
from src.modules.platform.adapters.outbound.persistence.repositories.user_repository import (
    SqlAlchemyUserRepository,
)
from src.modules.platform.adapters.outbound.persistence.unit_of_work import SqlAlchemyUnitOfWork
from src.modules.platform.application.dto.api_key_dto import CreateApiKeyCommand
from src.modules.platform.application.use_cases.api_key.create_api_key import CreateApiKey
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.services.agent_policy import AGENT_CONSENT_VERSION
from src.modules.platform.domain.value_objects.permission import Permission
from src.modules.platform.infrastructure.security.hashing import aget_hash
from src.shared_kernel.domain.services.clock import now_utc
from tests.integration._mcp_helpers import give_agent_consent
from tests.integration._mcp_helpers import list_tool_names
from tests.integration._mcp_helpers import mint_agent_token
from tests.integration._mcp_helpers import rpc
from tests.integration._mcp_helpers import save_agent_settings
from tests.integration._mcp_helpers import seed_security
from tests.integration.conftest import auth_headers

SETTINGS = "/api/v1/web/admin/settings/agents"
CONSENT = "/api/v1/web/users/me/agent-consent"
_CSRF = {"X-Requested-With": "glados"}


@pytest.fixture(autouse=True)
async def agents_seeded(db: AsyncSession) -> None:
    """The seeded agent settings: switched off and not approved."""
    await save_agent_settings(db, enabled=False, approved_providers="", processing_approved_at=None)


@pytest.fixture
async def owner(create_user: Callable[..., Awaitable[User]]) -> User:
    return await create_user(
        username="planner",
        email="planner@example.com",
        permissions=[Permission.WRITE_PAT, Permission.USE_MCP, Permission.MANAGE_API_KEYS],
    )


@pytest.fixture
async def admin(create_user: Callable[..., Awaitable[User]]) -> User:
    return await create_user(
        username="admin",
        email="admin@example.com",
        permissions=[Permission.READ_SETTINGS, Permission.WRITE_SETTINGS],
    )


async def _put_settings(client: httpx.AsyncClient, admin: User, **fields: object) -> httpx.Response:
    return await client.put(SETTINGS, json=fields, headers={**_CSRF, **await auth_headers(admin)})


# ── The company's approval ────────────────────────────────────────────


async def test_agent_access_cannot_be_switched_on_without_the_approval(
    client: httpx.AsyncClient, admin: User
) -> None:
    response = await _put_settings(client, admin, enabled=True)

    assert response.status_code == 422
    assert response.json()["code"] == "AgentAccessNotApprovedError"


async def test_an_approval_must_name_the_providers(client: httpx.AsyncClient, admin: User) -> None:
    response = await _put_settings(client, admin, processing_approved=True, approved_providers=" ")

    assert response.status_code == 422
    assert response.json()["code"] == "AgentAccessNotApprovedError"


async def test_approving_records_when_and_keeps_it_across_unrelated_changes(
    client: httpx.AsyncClient, admin: User
) -> None:
    approve = {"enabled": True, "processing_approved": True, "approved_providers": "Claude"}

    first = await _put_settings(client, admin, **approve)
    budget = await _put_settings(client, admin, **approve, calls_per_minute=60)

    assert first.status_code == 200
    assert first.json()["processing_approved_at"] is not None
    assert budget.json()["processing_approved_at"] == first.json()["processing_approved_at"]


@pytest.mark.parametrize(
    "change",
    [
        {"approved_providers": "Claude and Copilot"},
        {"ai_policy_url": "https://intranet.example.com/ai-policy"},
        {"include_person_names": True},
        {"include_costs": True},
    ],
)
async def test_changing_what_users_consented_to_renews_the_approval(
    client: httpx.AsyncClient, admin: User, change: dict[str, object]
) -> None:
    approve = {"enabled": True, "processing_approved": True, "approved_providers": "Claude"}

    first = await _put_settings(client, admin, **approve)
    changed = await _put_settings(client, admin, **{**approve, **change})

    assert changed.status_code == 200
    assert changed.json()["processing_approved_at"] > first.json()["processing_approved_at"]


async def test_withdrawing_the_approval_clears_it(client: httpx.AsyncClient, admin: User) -> None:
    await _put_settings(
        client, admin, enabled=True, processing_approved=True, approved_providers="Claude"
    )

    withdrawn = await _put_settings(client, admin, approved_providers="Claude")

    assert withdrawn.status_code == 200
    assert withdrawn.json()["processing_approved_at"] is None
    assert withdrawn.json()["enabled"] is False


async def test_an_ai_policy_link_with_a_query_is_refused(
    client: httpx.AsyncClient, admin: User
) -> None:
    response = await _put_settings(client, admin, ai_policy_url="https://example.com/p?id=1")

    assert response.status_code == 422


async def test_an_unapproved_switched_on_row_refuses_every_agent(
    client: httpx.AsyncClient, db: AsyncSession, owner: User
) -> None:
    await save_agent_settings(db, processing_approved_at=None)
    token = await mint_agent_token(db, owner, [Permission.USE_MCP])

    response = await rpc(client, token, "tools/list")

    assert response.status_code == 403
    assert response.json()["code"] == "AgentAccessDisabledError"


# ── The user's consent at the door ────────────────────────────────────


async def test_a_pat_of_a_user_without_consent_is_refused(
    client: httpx.AsyncClient, db: AsyncSession, owner: User
) -> None:
    await save_agent_settings(db)
    token = await mint_agent_token(db, owner, [Permission.USE_MCP], consent=False)

    response = await rpc(client, token, "tools/list")

    assert response.status_code == 403
    assert response.json()["code"] == "AgentConsentRequiredError"


async def test_a_consent_older_than_the_approval_is_refused(
    client: httpx.AsyncClient, db: AsyncSession, owner: User
) -> None:
    await save_agent_settings(db)
    token = await mint_agent_token(db, owner, [Permission.USE_MCP])
    await save_agent_settings(db, processing_approved_at=now_utc() + timedelta(seconds=1))

    response = await rpc(client, token, "tools/list")

    assert response.status_code == 403
    assert response.json()["code"] == "AgentConsentRequiredError"


async def test_a_consent_to_an_older_text_is_refused(
    client: httpx.AsyncClient, db: AsyncSession, owner: User
) -> None:
    await save_agent_settings(db)
    token = await mint_agent_token(db, owner, [Permission.USE_MCP], consent=False)
    await give_agent_consent(db, owner, version=AGENT_CONSENT_VERSION - 1)

    response = await rpc(client, token, "tools/list")

    assert response.status_code == 403
    assert response.json()["code"] == "AgentConsentRequiredError"


async def test_an_api_key_needs_no_personal_consent(
    client: httpx.AsyncClient, db: AsyncSession, owner: User
) -> None:
    await save_agent_settings(db)
    await seed_security(db, enable_api_key_auth=True)
    created = await CreateApiKey(
        SqlAlchemyApiKeyRepository(db),
        SqlAlchemyUserRepository(db),
        SqlAlchemyUnitOfWork(db),
        settings_repo=SqlAlchemyAdminSettingsRepository(db),
        hash_password_fn=aget_hash,
    ).execute(
        actor=owner,
        cmd=CreateApiKeyCommand(
            name="nightly", permissions=[Permission.USE_MCP], expires_in_days=30
        ),
    )

    assert "my_notifications" in await list_tool_names(client, created.key)


# ── Giving and withdrawing ────────────────────────────────────────────


async def test_the_status_shows_the_terms_and_the_missing_consent(
    client: httpx.AsyncClient, db: AsyncSession, owner: User
) -> None:
    await save_agent_settings(db, approved_providers="Claude", include_costs=True)

    response = await client.get(CONSENT, headers=await auth_headers(owner))

    assert response.status_code == 200
    body = response.json()
    assert body["access_ready"] is True and body["may_use_agents"] is True
    assert body["approved_providers"] == "Claude"
    assert body["include_costs"] is True and body["include_person_names"] is False
    assert body["consent_version"] == AGENT_CONSENT_VERSION
    assert body["consented_at"] is None and body["consent_current"] is False


async def test_giving_consent_lets_the_users_agent_in(
    client: httpx.AsyncClient, db: AsyncSession, owner: User
) -> None:
    await save_agent_settings(db)
    token = await mint_agent_token(db, owner, [Permission.USE_MCP], consent=False)

    given = await client.put(
        CONSENT,
        json={"consent_version": AGENT_CONSENT_VERSION},
        headers={**_CSRF, **await auth_headers(owner)},
    )

    assert given.status_code == 200
    assert given.json()["consent_current"] is True
    assert (await rpc(client, token, "tools/list")).status_code == 200


async def test_consent_to_another_text_version_is_refused(
    client: httpx.AsyncClient, db: AsyncSession, owner: User
) -> None:
    await save_agent_settings(db)

    response = await client.put(
        CONSENT,
        json={"consent_version": AGENT_CONSENT_VERSION + 1},
        headers={**_CSRF, **await auth_headers(owner)},
    )

    assert response.status_code == 422
    assert response.json()["code"] == "AgentConsentOutdatedError"


async def test_consent_needs_use_mcp(
    client: httpx.AsyncClient, db: AsyncSession, create_user: Callable[..., Awaitable[User]]
) -> None:
    await save_agent_settings(db)
    user = await create_user(permissions=[Permission.WRITE_PAT])

    response = await client.put(
        CONSENT,
        json={"consent_version": AGENT_CONSENT_VERSION},
        headers={**_CSRF, **await auth_headers(user)},
    )

    assert response.status_code == 403


async def test_consent_needs_approved_and_switched_on_access(
    client: httpx.AsyncClient, db: AsyncSession, owner: User
) -> None:
    await save_agent_settings(db, enabled=False)

    response = await client.put(
        CONSENT,
        json={"consent_version": AGENT_CONSENT_VERSION},
        headers={**_CSRF, **await auth_headers(owner)},
    )

    assert response.status_code == 403
    assert response.json()["code"] == "AgentAccessDisabledError"


async def test_withdrawing_revokes_the_agent_tokens_only_and_works_while_access_is_off(
    client: httpx.AsyncClient, db: AsyncSession, owner: User
) -> None:
    await save_agent_settings(db)
    await mint_agent_token(db, owner, [Permission.USE_MCP], name="agent")
    await mint_agent_token(db, owner, [Permission.WRITE_PAT], name="script", consent=False)
    await save_agent_settings(db, enabled=False)

    response = await client.delete(CONSENT, headers={**_CSRF, **await auth_headers(owner)})

    assert response.status_code == 200
    assert response.json()["consent_current"] is False
    db.expire_all()
    still_active = await SqlAlchemyPatRepository(db).list_unrevoked_unexpired(user_id=owner.id)
    assert [t.name for t in still_active] == ["script"]
