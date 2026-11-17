"""
The API-key surface's trigger config read (GET {API_KEY}/pdm/config) end
to end: resolves the configured vault's workflows through a faked
IPdmGateway (same dependency-override pattern as
test_api_key_pdm_validate.py) and returns the vault name plus the
deduplicated release-state names. Never writes anything, never fires an
event; it is a synchronous read, the same posture as the validate endpoint.
"""

import dataclasses
from collections.abc import Awaitable
from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from src.bootstrap.adapters.outbound.persistence.repositories.admin_settings_repository import (
    SqlAlchemyAdminSettingsRepository,
)
from src.bootstrap.main import app
from src.modules.external_data.adapters.inbound.api.deps.services import get_pdm_gateway_factory
from src.modules.external_data.domain.value_objects.pdm_watched_folder import PdmWatchedFolder
from src.modules.external_data.ports.outbound.pdm_gateway_port import PdmAuthResult
from src.modules.external_data.ports.outbound.pdm_gateway_port import PdmWorkflow
from src.modules.external_data.ports.outbound.pdm_gateway_port import PdmWorkflowState
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

BASE = "/api/v1/key/pdm/config"

MADE_FOLDER = PdmWatchedFolder(path="\\Made-Parts", kind="made", recursive=True, enabled=True)


class FakeGateway:
    """Minimal IPdmGateway fake: only the methods GetPdmTriggerConfig
    actually calls (authenticate for PdmSessionService's own login, and
    workflows); see test_api_key_pdm_validate.py's own FakeGateway for
    the established shape this mirrors."""

    def __init__(self) -> None:
        self.workflows_result: list[PdmWorkflow] = []

    async def authenticate(self, username: str, password: str) -> PdmAuthResult:
        return PdmAuthResult(token="tok", user_id=1)

    async def workflows(self, token: str) -> list[PdmWorkflow]:
        return self.workflows_result


@pytest.fixture
def pdm_gateway():
    fake = FakeGateway()
    app.dependency_overrides[get_pdm_gateway_factory] = lambda: lambda connection: fake
    yield fake
    app.dependency_overrides.pop(get_pdm_gateway_factory, None)


@pytest.fixture(autouse=True)
async def _enable_api_key_auth(db: Session) -> None:
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


async def _seed_pdm(db: Session, *, enabled: bool = True):
    """Every current AdminPdmSettings field left at whatever save_pdm's
    already-stored row carries, only the fields this endpoint reads are
    overridden, mirroring test_api_key_pdm_validate.py's own `_seed_pdm`."""
    repo = SqlAlchemyAdminSettingsRepository(db)
    current = await repo.get_pdm()
    return await repo.save_pdm(
        dataclasses.replace(
            current,
            enabled=enabled,
            base_url="http://pdm-host:65453",
            vault_name="MyVault",
            username="svc-account",
            password="secret",
            watched_folders=[MADE_FOLDER],
            made_released_state_ids=[10],
            bought_released_state_ids=[11],
            vault_id="V1",
        )
    )


@pytest.fixture
async def key_owner(create_user) -> User:
    return await create_user(
        username="pdm-config-owner",
        email="pdm-config-owner@example.com",
        permissions=[Permission.MANAGE_API_KEYS, Permission.USE_PDM_ADDIN],
    )


@pytest.fixture
def mint_api_key(db: Session, key_owner: User) -> Callable[[list[str]], Awaitable[str]]:
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
    async def test_returns_vault_name_and_release_state_names(
        self,
        db: Session,
        client: TestClient,
        mint_api_key: Callable[[list[str]], Awaitable[str]],
        pdm_gateway: FakeGateway,
    ) -> None:
        await _seed_pdm(db)
        pdm_gateway.workflows_result = [
            PdmWorkflow(
                workflow_id=1,
                workflow_name="Made Workflow",
                states=(
                    PdmWorkflowState(state_id=10, state_name="Released"),
                    PdmWorkflowState(state_id=20, state_name="Obsolete"),
                ),
            ),
            PdmWorkflow(
                workflow_id=2,
                workflow_name="Bought Workflow",
                states=(PdmWorkflowState(state_id=11, state_name="Approved"),),
            ),
        ]
        key = await mint_api_key([Permission.USE_PDM_ADDIN])

        resp = await client.get(BASE, headers={"X-Api-Key": key})

        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["vault_name"] == "MyVault"
        assert body["release_state_names"] == ["Approved", "Released"]


class TestForbidden:
    async def test_key_without_trigger_pdm_sync_is_rejected(
        self, db: Session, client: TestClient, mint_api_key: Callable[[list[str]], Awaitable[str]]
    ) -> None:
        await _seed_pdm(db)
        key = await mint_api_key([])

        resp = await client.get(BASE, headers={"X-Api-Key": key})

        assert resp.status_code == 403


class TestNotEnabled:
    async def test_unconfigured_integration_is_rejected(
        self, client: TestClient, mint_api_key: Callable[[list[str]], Awaitable[str]]
    ) -> None:
        # No _seed_pdm call: the autouse bare row (enabled=False, blank
        # connection fields) is exactly the "not enabled and configured"
        # state this checks.
        key = await mint_api_key([Permission.USE_PDM_ADDIN])

        resp = await client.get(BASE, headers={"X-Api-Key": key})

        assert resp.status_code == 409
