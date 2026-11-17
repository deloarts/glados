"""
The PAT surface's PDM change-notification trigger (POST
/api/v1/pat/pdm/files/changed/batch) end to end, signed in with a real
token minted through CreatePat: 202 with one PdmFileChangeRequested per
distinct file, attributed to the token's owner, 401 without a token, 403
for a token without use:pdm_addin even when its owner holds it, 400 for
the wrong vault, 409 while the integration is off, 422 for an empty or
oversized batch and 429 once the owner's trigger budget is spent. The body
and answer are the API-key surface's, see test_api_key_pdm_trigger.py.
"""

import dataclasses
from collections.abc import Awaitable
from collections.abc import Callable
from collections.abc import Iterator

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.bootstrap.adapters.outbound.persistence.repositories.admin_settings_repository import (
    SqlAlchemyAdminSettingsRepository,
)
from src.bootstrap.main import app
from src.modules.external_data.adapters.inbound.api.deps.services import (
    get_pdm_trigger_rate_limiter,
)
from src.modules.external_data.application.services.pdm_trigger_rate_limiter import (
    PdmTriggerRateLimiter,
)
from src.modules.external_data.domain.events.pdm_events import PdmFileChangeRequested
from src.modules.platform.adapters.outbound.persistence.repositories.pat_repository import (
    SqlAlchemyPatRepository,
)
from src.modules.platform.adapters.outbound.persistence.unit_of_work import SqlAlchemyUnitOfWork
from src.modules.platform.application.dto.pat_dto import CreatePatCommand
from src.modules.platform.application.use_cases.pat.create_pat import CreatePat
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.value_objects.permission import Permission

_URL = "/api/v1/pat/pdm/files/changed/batch"


async def _seed_pdm_enabled(db: AsyncSession) -> None:
    """Enables the integration on top of the autouse bare row, with the
    connection fields is_pdm_enabled requires and the vault name the
    trigger compares against."""
    repo = SqlAlchemyAdminSettingsRepository(db)
    await repo.save_pdm(
        dataclasses.replace(
            await repo.get_pdm(),
            enabled=True,
            base_url="http://pdm-host:65453",
            vault_name="MyVault",
            username="svc-account",
            password="secret",
        )
    )
    await db.commit()


@pytest.fixture(autouse=True)
def rate_limiter() -> Iterator[PdmTriggerRateLimiter]:
    """A fresh limiter per test, so the budget one test spends never makes
    an unrelated later test see a 429."""
    limiter = PdmTriggerRateLimiter()
    app.dependency_overrides[get_pdm_trigger_rate_limiter] = lambda: limiter
    yield limiter
    app.dependency_overrides.pop(get_pdm_trigger_rate_limiter, None)


@pytest.fixture
async def pat_owner(create_user) -> User:
    """Holds WRITE_PAT (required to mint a token at all) and
    USE_PDM_ADDIN (a token's scopes are capped at its owner's own
    permissions)."""
    return await create_user(
        username="pat-owner-pdm-trigger",
        email="pat-owner-pdm-trigger@example.com",
        permissions=[Permission.WRITE_PAT, Permission.USE_PDM_ADDIN],
    )


@pytest.fixture
def mint_pat(db: AsyncSession, pat_owner: User) -> Callable[[list[str]], Awaitable[str]]:
    async def _mint(permissions: list[str]) -> str:
        result = await CreatePat(
            SqlAlchemyPatRepository(db),
            settings_repo=SqlAlchemyAdminSettingsRepository(db),
            uow=SqlAlchemyUnitOfWork(db),
        ).execute(
            actor=pat_owner,
            cmd=CreatePatCommand(name="PDM Addin", permissions=permissions),
        )
        return result.token

    return _mint


class TestHappyPath:
    async def test_batch_queues_one_refresh_per_distinct_file_for_the_owner(
        self,
        db: AsyncSession,
        client: httpx.AsyncClient,
        mint_pat: Callable[[list[str]], Awaitable[str]],
        pat_owner: User,
        published_events: list[object],
    ) -> None:
        await _seed_pdm_enabled(db)
        token = await mint_pat([Permission.USE_PDM_ADDIN])

        resp = await client.post(
            _URL,
            json={
                "vault_name": "MyVault",
                "files": [
                    {"file_id": 1, "version": 3},
                    {"file_id": 2, "path": "Made-Parts\\b.sldprt"},
                    {"file_id": 1, "version": 4},
                ],
            },
            headers={"X-Api-Key": token},
        )

        assert resp.status_code == 202, resp.text
        assert resp.json() == {"accepted": 2}
        pdm_events = [e for e in published_events if isinstance(e, PdmFileChangeRequested)]
        assert {(e.file_id, e.path, e.version) for e in pdm_events} == {
            (1, None, 4),
            (2, "Made-Parts\\b.sldprt", None),
        }
        assert {e.requested_by_id for e in pdm_events} == {pat_owner.id}
        assert {e.source for e in pdm_events} == {"file_trigger"}

    async def test_reason_state_and_the_owners_name_travel_on_the_event(
        self,
        db: AsyncSession,
        client: httpx.AsyncClient,
        mint_pat: Callable[[list[str]], Awaitable[str]],
        pat_owner: User,
        published_events: list[object],
    ) -> None:
        await _seed_pdm_enabled(db)
        token = await mint_pat([Permission.USE_PDM_ADDIN])

        resp = await client.post(
            _URL,
            json={
                "vault_name": "MyVault",
                "files": [
                    {"file_id": 1, "reason": "state_change", "state": "Released"},
                    {"file_id": 2},
                ],
            },
            headers={"X-Api-Key": token},
        )

        assert resp.status_code == 202, resp.text
        pdm_events = {
            e.file_id: e for e in published_events if isinstance(e, PdmFileChangeRequested)
        }
        assert (pdm_events[1].reason, pdm_events[1].state) == ("state_change", "Released")
        assert (pdm_events[2].reason, pdm_events[2].state) == (None, None)
        assert {e.requested_by_name for e in pdm_events.values()} == {pat_owner.full_name}

    async def test_add_and_copy_are_accepted_reasons(
        self,
        db: AsyncSession,
        client: httpx.AsyncClient,
        mint_pat: Callable[[list[str]], Awaitable[str]],
        published_events: list[object],
    ) -> None:
        await _seed_pdm_enabled(db)
        token = await mint_pat([Permission.USE_PDM_ADDIN])

        resp = await client.post(
            _URL,
            json={
                "vault_name": "MyVault",
                "files": [{"file_id": 1, "reason": "add"}, {"file_id": 2, "reason": "copy"}],
            },
            headers={"X-Api-Key": token},
        )

        assert resp.status_code == 202, resp.text
        assert {
            (e.file_id, e.reason) for e in published_events if isinstance(e, PdmFileChangeRequested)
        } == {(1, "add"), (2, "copy")}

    async def test_an_unknown_reason_is_422(
        self,
        db: AsyncSession,
        client: httpx.AsyncClient,
        mint_pat: Callable[[list[str]], Awaitable[str]],
    ) -> None:
        await _seed_pdm_enabled(db)
        token = await mint_pat([Permission.USE_PDM_ADDIN])

        resp = await client.post(
            _URL,
            json={"vault_name": "MyVault", "files": [{"file_id": 1, "reason": "checkout"}]},
            headers={"X-Api-Key": token},
        )

        assert resp.status_code == 422


class TestAuth:
    async def test_missing_token_is_401(self, client: httpx.AsyncClient) -> None:
        resp = await client.post(_URL, json={"vault_name": "MyVault", "files": [{"file_id": 1}]})

        assert resp.status_code == 401

    async def test_token_without_use_pdm_addin_is_403(
        self,
        db: AsyncSession,
        client: httpx.AsyncClient,
        mint_pat: Callable[[list[str]], Awaitable[str]],
        published_events: list[object],
    ) -> None:
        await _seed_pdm_enabled(db)
        # The owner holds use:pdm_addin, the token does not: the token's
        # own scope decides.
        token = await mint_pat([])

        resp = await client.post(
            _URL,
            json={"vault_name": "MyVault", "files": [{"file_id": 1}]},
            headers={"X-Api-Key": token},
        )

        assert resp.status_code == 403
        assert not [e for e in published_events if isinstance(e, PdmFileChangeRequested)]


class TestRejected:
    async def test_wrong_vault_is_400(
        self,
        db: AsyncSession,
        client: httpx.AsyncClient,
        mint_pat: Callable[[list[str]], Awaitable[str]],
    ) -> None:
        await _seed_pdm_enabled(db)
        token = await mint_pat([Permission.USE_PDM_ADDIN])

        resp = await client.post(
            _URL,
            json={"vault_name": "Other", "files": [{"file_id": 1}]},
            headers={"X-Api-Key": token},
        )

        assert resp.status_code == 400

    async def test_unconfigured_integration_is_409(
        self, client: httpx.AsyncClient, mint_pat: Callable[[list[str]], Awaitable[str]]
    ) -> None:
        # No _seed_pdm_enabled call: the autouse bare row is disabled.
        token = await mint_pat([Permission.USE_PDM_ADDIN])

        resp = await client.post(
            _URL,
            json={"vault_name": "MyVault", "files": [{"file_id": 1}]},
            headers={"X-Api-Key": token},
        )

        assert resp.status_code == 409

    async def test_empty_or_oversized_batch_is_422(
        self,
        db: AsyncSession,
        client: httpx.AsyncClient,
        mint_pat: Callable[[list[str]], Awaitable[str]],
    ) -> None:
        await _seed_pdm_enabled(db)
        token = await mint_pat([Permission.USE_PDM_ADDIN])

        empty = await client.post(
            _URL,
            json={"vault_name": "MyVault", "files": []},
            headers={"X-Api-Key": token},
        )
        oversized = await client.post(
            _URL,
            json={"vault_name": "MyVault", "files": [{"file_id": i} for i in range(1, 102)]},
            headers={"X-Api-Key": token},
        )

        assert empty.status_code == 422
        assert oversized.status_code == 422


class TestRateLimit:
    async def test_batch_beyond_the_owners_budget_is_429(
        self,
        db: AsyncSession,
        client: httpx.AsyncClient,
        mint_pat: Callable[[list[str]], Awaitable[str]],
        rate_limiter: PdmTriggerRateLimiter,
    ) -> None:
        await _seed_pdm_enabled(db)
        token = await mint_pat([Permission.USE_PDM_ADDIN])
        body = {"vault_name": "MyVault", "files": [{"file_id": i} for i in range(1, 101)]}

        first = [await client.post(_URL, json=body, headers={"X-Api-Key": token}) for _ in range(3)]
        fourth = await client.post(_URL, json=body, headers={"X-Api-Key": token})

        assert [r.status_code for r in first] == [202, 202, 202]
        assert fourth.status_code == 429
