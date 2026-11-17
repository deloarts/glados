"""
The API-key surface's PDM change-notification trigger (POST
{API_KEY}/pdm/files/changed) end to end: 202 + a PdmFileChangeRequested
event on the transactional bus for the happy path, 403 without
use:pdm_addin, 409 while the integration is not enabled and configured,
422 when neither file_id nor path is supplied. No PDM Web API call is ever
made: the endpoint only stages an event, see RequestPdmFileRefresh.
"""

from collections.abc import Awaitable
from collections.abc import Callable

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.bootstrap.adapters.outbound.persistence.repositories.admin_settings_repository import (
    SqlAlchemyAdminSettingsRepository,
)
from src.modules.external_data.domain.entities.admin_settings.pdm import AdminPdmSettings
from src.modules.external_data.domain.events.pdm_events import PdmFileChangeRequested
from src.modules.platform.adapters.outbound.persistence.repositories.api_key_repository import (
    SqlAlchemyApiKeyRepository,
)
from src.modules.platform.adapters.outbound.persistence.repositories.user_repository import (
    SqlAlchemyUserRepository,
)
from src.modules.platform.adapters.outbound.persistence.unit_of_work import SqlAlchemyUnitOfWork
from src.modules.platform.application.dto.api_key_dto import CreateApiKeyCommand
from src.modules.platform.application.use_cases.api_key.create_api_key import CreateApiKey
from src.modules.platform.domain.entities.admin_settings.security import AdminSecuritySettings
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.value_objects.permission import Permission
from src.modules.platform.infrastructure.security.hashing import aget_hash

BASE = "/api/v1/key/pdm/files/changed"


@pytest.fixture(autouse=True)
async def _enable_api_key_auth(db: AsyncSession) -> None:
    """`enable_api_key_auth` defaults False, see test_api_key_surface.py's
    own fixture of the same shape."""
    await SqlAlchemyAdminSettingsRepository(db).save_security(
        AdminSecuritySettings(
            id=1,
            enforce_totp=False,
            allow_rfid_login=True,
            allow_local_login=True,
            enable_api_key_auth=True,
            min_password_length=8,
            session_timeout_minutes=1440,
            totp_trusted_device_days=30,
            max_login_attempts=5,
            lockout_duration_minutes=15,
            token_max_lifetime_days=3650,
        )
    )
    await db.commit()


async def _seed_pdm(db: AsyncSession, **overrides: object) -> None:
    """Seeds admin_pdm_settings on top of the autouse bare row (see
    tests/integration/conftest.py's `_seed_admin_settings`), same pattern
    as test_api_admin_settings_pdm_files.py's `_seed_pdm_vault_name`."""
    repo = SqlAlchemyAdminSettingsRepository(db)
    current = await repo.get_pdm()
    defaults: dict[str, object] = dict(
        id=1,
        made_item_variable_map=current.made_item_variable_map,
        bought_item_variable_map=current.bought_item_variable_map,
        enabled=True,
        base_url="http://pdm-host:65453",
        vault_name="MyVault",
        username="svc-account",
        password="secret",
        verify_certificate=True,
        timeout_seconds=15,
        session_token=None,
        session_user_id=None,
        session_obtained_at=None,
        watched_folders=current.watched_folders,
        made_released_state_ids=current.made_released_state_ids,
        made_obsolete_state_ids=current.made_obsolete_state_ids,
        made_replaced_state_ids=current.made_obsolete_state_ids,
        bought_released_state_ids=current.bought_released_state_ids,
        bought_obsolete_state_ids=current.bought_obsolete_state_ids,
        bought_replaced_state_ids=current.bought_obsolete_state_ids,
        poll_interval_minutes=current.poll_interval_minutes,
        vault_id=current.vault_id,
        cad_items_read_only=current.cad_items_read_only,
        last_poll_at=current.last_poll_at,
        last_poll_error=current.last_poll_error,
        last_poll_summary=current.last_poll_summary,
        writeback_enabled=current.writeback_enabled,
    )
    defaults.update(overrides)
    await repo.save_pdm(
        AdminPdmSettings(
            **defaults,
            made_item_extensions=["sldprt"],
            bought_item_extensions=["sldprt", "sldasm"],
            document_categories={"pdf": "drawing", "dxf": "dxf", "step": "step", "stp": "step"},
            thumbnails_enabled=False,
            stuck_after_days=current.stuck_after_days,
            reconcile_requested_deep=current.reconcile_requested_deep,
            required_fields=current.required_fields,
        )
    )  # type: ignore[arg-type]
    await db.commit()


@pytest.fixture
async def key_owner(create_user) -> User:
    """Holds both MANAGE_API_KEYS (required to mint a key at all) and
    USE_PDM_ADDIN (a key's granted scopes are capped at its issuer's
    own permissions, see ApiKeyRules.assert_permissions_allowed)."""
    return await create_user(
        username="pdm-addin-owner",
        email="pdm-addin-owner@example.com",
        permissions=[Permission.MANAGE_API_KEYS, Permission.USE_PDM_ADDIN],
    )


@pytest.fixture
def mint_api_key(db: AsyncSession, key_owner: User) -> Callable[[list[str]], Awaitable[str]]:
    async def _mint(permissions: list[str]) -> str:
        result = await CreateApiKey(
            SqlAlchemyApiKeyRepository(db),
            SqlAlchemyUserRepository(db),
            SqlAlchemyUnitOfWork(db),
            settings_repo=SqlAlchemyAdminSettingsRepository(db),
            hash_password_fn=aget_hash,
        ).execute(
            actor=key_owner,
            cmd=CreateApiKeyCommand(name="pdm-addin", permissions=permissions, expires_in_days=30),
        )
        return result.key

    return _mint


class TestHappyPath:
    async def test_trigger_by_file_id_is_accepted_and_publishes_event(
        self,
        db: AsyncSession,
        client: httpx.AsyncClient,
        mint_api_key: Callable[[list[str]], Awaitable[str]],
        published_events: list[object],
    ) -> None:
        await _seed_pdm(db)
        key = await mint_api_key([Permission.USE_PDM_ADDIN])

        resp = await client.post(
            BASE,
            json={"vault_name": "MyVault", "file_id": 4242, "version": 7},
            headers={"X-Api-Key": key},
        )

        assert resp.status_code == 202, resp.text
        assert resp.json() == {"accepted": True}

        pdm_events = [e for e in published_events if isinstance(e, PdmFileChangeRequested)]
        assert len(pdm_events) == 1
        event = pdm_events[0]
        assert event.vault_name == "MyVault"
        assert event.file_id == 4242
        assert event.path is None
        assert event.version == 7

    async def test_trigger_by_path_is_accepted(
        self,
        db: AsyncSession,
        client: httpx.AsyncClient,
        mint_api_key: Callable[[list[str]], Awaitable[str]],
        published_events: list[object],
    ) -> None:
        await _seed_pdm(db)
        key = await mint_api_key([Permission.USE_PDM_ADDIN])

        resp = await client.post(
            BASE,
            json={"vault_name": "MyVault", "path": "\\Made-Parts\\part.sldprt"},
            headers={"X-Api-Key": key},
        )

        assert resp.status_code == 202, resp.text
        pdm_events = [e for e in published_events if isinstance(e, PdmFileChangeRequested)]
        assert len(pdm_events) == 1
        assert pdm_events[0].path == "\\Made-Parts\\part.sldprt"


class TestForbidden:
    async def test_key_without_trigger_pdm_sync_is_rejected(
        self,
        db: AsyncSession,
        client: httpx.AsyncClient,
        mint_api_key: Callable[[list[str]], Awaitable[str]],
    ) -> None:
        await _seed_pdm(db)
        key = await mint_api_key([])  # no permissions at all

        resp = await client.post(
            BASE, json={"vault_name": "MyVault", "file_id": 1}, headers={"X-Api-Key": key}
        )

        assert resp.status_code == 403


class TestNotEnabled:
    async def test_unconfigured_integration_is_rejected(
        self, client: httpx.AsyncClient, mint_api_key: Callable[[list[str]], Awaitable[str]]
    ) -> None:
        # No _seed_pdm call: the autouse bare row (enabled=False, blank
        # connection fields) is exactly the "not enabled and configured"
        # state this checks.
        key = await mint_api_key([Permission.USE_PDM_ADDIN])

        resp = await client.post(
            BASE, json={"vault_name": "MyVault", "file_id": 1}, headers={"X-Api-Key": key}
        )

        assert resp.status_code == 409


class TestValidation:
    async def test_neither_file_id_nor_path_is_422(
        self,
        db: AsyncSession,
        client: httpx.AsyncClient,
        mint_api_key: Callable[[list[str]], Awaitable[str]],
    ) -> None:
        await _seed_pdm(db)
        key = await mint_api_key([Permission.USE_PDM_ADDIN])

        resp = await client.post(BASE, json={"vault_name": "MyVault"}, headers={"X-Api-Key": key})

        assert resp.status_code == 422


class TestBatch:
    async def test_batch_queues_one_refresh_per_distinct_file(
        self,
        db: AsyncSession,
        client: httpx.AsyncClient,
        mint_api_key: Callable[[list[str]], Awaitable[str]],
        published_events: list[object],
    ) -> None:
        await _seed_pdm(db)
        key = await mint_api_key([Permission.USE_PDM_ADDIN])

        resp = await client.post(
            f"{BASE}/batch",
            json={
                "vault_name": "MyVault",
                "files": [
                    {"file_id": 1, "version": 3},
                    {"file_id": 2, "path": "\\Made-Parts\\b.sldprt"},
                    {"file_id": 1, "version": 4},
                ],
            },
            headers={"X-Api-Key": key},
        )

        assert resp.status_code == 202, resp.text
        assert resp.json() == {"accepted": 2}
        pdm_events = [e for e in published_events if isinstance(e, PdmFileChangeRequested)]
        assert {(e.file_id, e.version) for e in pdm_events} == {(1, 4), (2, None)}

    async def test_wrong_vault_is_400(
        self,
        db: AsyncSession,
        client: httpx.AsyncClient,
        mint_api_key: Callable[[list[str]], Awaitable[str]],
    ) -> None:
        await _seed_pdm(db)
        key = await mint_api_key([Permission.USE_PDM_ADDIN])

        resp = await client.post(
            f"{BASE}/batch",
            json={"vault_name": "Other", "files": [{"file_id": 1}]},
            headers={"X-Api-Key": key},
        )

        assert resp.status_code == 400

    async def test_empty_or_oversized_batch_is_422(
        self,
        db: AsyncSession,
        client: httpx.AsyncClient,
        mint_api_key: Callable[[list[str]], Awaitable[str]],
    ) -> None:
        await _seed_pdm(db)
        key = await mint_api_key([Permission.USE_PDM_ADDIN])

        empty = await client.post(
            f"{BASE}/batch",
            json={"vault_name": "MyVault", "files": []},
            headers={"X-Api-Key": key},
        )
        oversized = await client.post(
            f"{BASE}/batch",
            json={"vault_name": "MyVault", "files": [{"file_id": i} for i in range(1, 102)]},
            headers={"X-Api-Key": key},
        )

        assert empty.status_code == 422
        assert oversized.status_code == 422
