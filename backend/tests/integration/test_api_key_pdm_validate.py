"""
The API-key surface's pre-release validation endpoint (POST
{API_KEY}/pdm/files/{file_id}/validate, docs/reference/pdm-ingest.md section
8) end to end: resolves a file through a faked IPdmGateway (same
dependency-override pattern as test_api_admin_settings_pdm.py), matches it
against a watched folder, and returns the ValidatePdmPayload verdict.
Never stages an event, never writes a snapshot row, unlike
POST {API_KEY}/pdm/files/changed (test_api_key_pdm_trigger.py); this is a
synchronous read.
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
from src.modules.catalogue.domain.entities.admin_settings.orders import AdminOrderSettings
from src.modules.external_data.adapters.inbound.api.deps.services import get_pdm_gateway_factory
from src.modules.external_data.domain.entities.admin_settings.pdm import AdminPdmSettings
from src.modules.external_data.domain.value_objects.pdm_watched_folder import PdmWatchedFolder
from src.modules.external_data.ports.outbound.pdm_gateway_port import PdmAuthResult
from src.modules.external_data.ports.outbound.pdm_gateway_port import PdmConfigVariables
from src.modules.external_data.ports.outbound.pdm_gateway_port import PdmObjectInfo
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

BASE = "/api/v1/key/pdm/files"

MADE_FOLDER = PdmWatchedFolder(path="\\Made-Parts", kind="made", recursive=True, enabled=True)
PATTERN = r"CAD-\d+"


class FakeGateway:
    """Minimal IPdmGateway fake: only the methods ValidatePdmFile actually
    calls (authenticate for PdmSessionService's own login, files_info,
    file_variables); see test_refresh_pdm_file.py's FakeGateway for the
    established shape this mirrors."""

    def __init__(self) -> None:
        self.by_id: dict[int, PdmObjectInfo] = {}
        self.variables: dict[int, list[PdmConfigVariables]] = {}

    async def authenticate(self, username: str, password: str) -> PdmAuthResult:
        return PdmAuthResult(token="tok", user_id=1)

    async def files_info(self, token: str, file_ids: list[int]) -> list[PdmObjectInfo]:
        return [self.by_id[i] for i in file_ids if i in self.by_id]

    async def file_variables(
        self, token: str, file_id: int, version: int, folder_id: int
    ) -> list[PdmConfigVariables]:
        return self.variables.get(file_id, [])


def make_object(
    *,
    id: int = 100,
    name: str = "part.sldprt",
    path: str = "\\Made-Parts\\part.sldprt",
    version: int = 5,
    state: str = "Released",
    state_id: int = 10,
    parent_folder_id: int = 1,
) -> PdmObjectInfo:
    return PdmObjectInfo(
        id=id,
        name=name,
        size=0,
        modified_at=None,
        version=version,
        state=state,
        state_id=state_id,
        parent_folder_id=parent_folder_id,
        path=path,
        object_type=1,
        is_locked=False,
        locked_by=0,
        is_shared=False,
        is_toolbox=False,
        is_deleted=False,
    )


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


async def _seed_pdm(db: Session, *, enabled: bool = True) -> AdminPdmSettings:
    """Every current AdminPdmSettings field is explicit: the connection is
    fully configured and one watched folder covers the test file. Also
    creates the order-settings row: ValidatePdmPayload always loads both
    made-item and order settings regardless of kind (mirroring
    IngestPdmFile's own execute()), and unlike made-item settings the
    order row has no "bare row" autouse seed in
    tests/integration/conftest.py, since the request path never needed it
    before this endpoint existed. save_orders() upserts, so this creates
    the row from scratch."""
    repo = SqlAlchemyAdminSettingsRepository(db)
    await repo.save_orders(
        AdminOrderSettings(
            id=1,
            order_number_format="ORD-{yy}-{seq:05d}",
            part_number_format="PUR-{yy}-{seq:05d}",
            part_number_auto=False,
            part_number_editable=True,
            web_creation_allowed=True,
            pdm_part_number_pattern=PATTERN,
        )
    )
    await db.commit()
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
            made_obsolete_state_ids=[20],
            bought_released_state_ids=[10],
            bought_obsolete_state_ids=[20],
            vault_id="V1",
            # The stored default also requires `material` and a fabrication
            # step; these tests are about the verdict shape, not the
            # required-field rule (test_validate_pdm_payload.py covers that),
            # so only the locked set is left in play.
            required_fields={"made": [], "bought": []},
        )
    )


async def _seed_made_pattern(db: Session) -> None:
    repo = SqlAlchemyAdminSettingsRepository(db)
    await repo.save_made_items(
        dataclasses.replace(await repo.get_made_items(), pdm_part_number_pattern=PATTERN)
    )
    await db.commit()


@pytest.fixture
async def key_owner(create_user) -> User:
    return await create_user(
        username="pdm-validate-owner",
        email="pdm-validate-owner@example.com",
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
    async def test_made_create_verdict(
        self,
        db: Session,
        client: TestClient,
        mint_api_key: Callable[[list[str]], Awaitable[str]],
        pdm_gateway: FakeGateway,
    ) -> None:
        await _seed_pdm(db)
        await _seed_made_pattern(db)
        pdm_gateway.by_id[100] = make_object()
        pdm_gateway.variables[100] = [
            PdmConfigVariables(
                configuration_name="@",
                configuration_id=1,
                variables={
                    "PDM.PartNumber": "CAD-1001",
                    "PDM.Revision": "A",
                    # article_name is locked-required, never configurable off.
                    "Glados.ArticleName": "Bracket",
                },
            )
        ]
        key = await mint_api_key([Permission.USE_PDM_ADDIN])

        resp = await client.post(f"{BASE}/100/validate", headers={"X-Api-Key": key})

        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["ok"] is True
        assert body["kind"] == "made"
        assert body["part_number"] == "CAD-1001"
        assert body["would"] == "created"
        assert body["reasons"] == []

    async def test_reports_reasons_without_failing_the_request(
        self,
        db: Session,
        client: TestClient,
        mint_api_key: Callable[[list[str]], Awaitable[str]],
        pdm_gateway: FakeGateway,
    ) -> None:
        """No pattern configured -> a 200 with ok=False, not an error."""
        await _seed_pdm(db)  # pdm_part_number_pattern left at its blank default
        pdm_gateway.by_id[100] = make_object()
        pdm_gateway.variables[100] = [
            PdmConfigVariables(
                configuration_name="@",
                configuration_id=1,
                variables={"PDM.PartNumber": "CAD-1001", "PDM.Revision": "A"},
            )
        ]
        key = await mint_api_key([Permission.USE_PDM_ADDIN])

        resp = await client.post(f"{BASE}/100/validate", headers={"X-Api-Key": key})

        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["ok"] is False
        assert any("no external PDM part number pattern configured" in r for r in body["reasons"])


class TestForbidden:
    async def test_key_without_trigger_pdm_sync_is_rejected(
        self, db: Session, client: TestClient, mint_api_key: Callable[[list[str]], Awaitable[str]]
    ) -> None:
        await _seed_pdm(db)
        key = await mint_api_key([])

        resp = await client.post(f"{BASE}/100/validate", headers={"X-Api-Key": key})

        assert resp.status_code == 403


class TestNotEnabled:
    async def test_unconfigured_integration_is_rejected(
        self, client: TestClient, mint_api_key: Callable[[list[str]], Awaitable[str]]
    ) -> None:
        # No _seed_pdm call: the autouse bare row (enabled=False, blank
        # connection fields) is exactly the "not enabled and configured"
        # state this checks.
        key = await mint_api_key([Permission.USE_PDM_ADDIN])

        resp = await client.post(f"{BASE}/100/validate", headers={"X-Api-Key": key})

        assert resp.status_code == 409


class TestNotFound:
    async def test_unknown_file_id_is_404(
        self,
        db: Session,
        client: TestClient,
        mint_api_key: Callable[[list[str]], Awaitable[str]],
        pdm_gateway: FakeGateway,
    ) -> None:
        await _seed_pdm(db)
        key = await mint_api_key([Permission.USE_PDM_ADDIN])

        resp = await client.post(f"{BASE}/999/validate", headers={"X-Api-Key": key})

        assert resp.status_code == 404


class TestBatch:
    async def test_each_file_gets_its_own_outcome(
        self,
        db: Session,
        client: TestClient,
        mint_api_key: Callable[[list[str]], Awaitable[str]],
        pdm_gateway: FakeGateway,
    ) -> None:
        await _seed_pdm(db)
        await _seed_made_pattern(db)
        pdm_gateway.by_id[100] = make_object()
        pdm_gateway.variables[100] = [
            PdmConfigVariables(
                configuration_name="@",
                configuration_id=1,
                variables={
                    "PDM.PartNumber": "CAD-1001",
                    "PDM.Revision": "A",
                    "Glados.ArticleName": "Bracket",
                },
            )
        ]
        key = await mint_api_key([Permission.USE_PDM_ADDIN])

        resp = await client.post(
            f"{BASE}/validate/batch",
            json={"file_ids": [100, 999, 100]},
            headers={"X-Api-Key": key},
        )

        assert resp.status_code == 200, resp.text
        results = resp.json()["results"]
        assert [r["file_id"] for r in results] == [100, 999]
        assert results[0]["outcome"] == "validated"
        assert results[0]["validation"]["ok"] is True
        assert results[0]["validation"]["part_number"] == "CAD-1001"
        assert results[1]["outcome"] == "not_found"
        assert results[1]["validation"] is None

    async def test_empty_batch_is_422(
        self, db: Session, client: TestClient, mint_api_key: Callable[[list[str]], Awaitable[str]]
    ) -> None:
        await _seed_pdm(db)
        key = await mint_api_key([Permission.USE_PDM_ADDIN])

        resp = await client.post(
            f"{BASE}/validate/batch", json={"file_ids": []}, headers={"X-Api-Key": key}
        )

        assert resp.status_code == 422

    async def test_key_without_trigger_pdm_sync_is_rejected(
        self, db: Session, client: TestClient, mint_api_key: Callable[[list[str]], Awaitable[str]]
    ) -> None:
        await _seed_pdm(db)
        key = await mint_api_key([])

        resp = await client.post(
            f"{BASE}/validate/batch", json={"file_ids": [100]}, headers={"X-Api-Key": key}
        )

        assert resp.status_code == 403
