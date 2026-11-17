"""
The PAT surface's pre-release validation endpoint (POST
/api/v1/pat/pdm/validate, docs/reference/pdm-ingest.md section 8) end to
end: drives the real endpoint through the PAT auth chain (mint a real
token via CreatePat, same pattern as test_api_pat_field_mapping.py) with a
raw property bag, no vault round trip at all. Unlike the API-key surface
(test_api_key_pdm_validate.py), no IPdmGateway is ever touched here.
"""

import dataclasses
from collections.abc import Awaitable
from collections.abc import Callable
from datetime import UTC
from datetime import datetime

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.bootstrap.adapters.outbound.persistence.repositories.admin_settings_repository import (
    SqlAlchemyAdminSettingsRepository,
)
from src.modules.catalogue.adapters.outbound.persistence.repositories.bought_item_repository.item import (
    SqlAlchemyBoughtItemRepository,
)
from src.modules.catalogue.domain.entities.admin_settings.orders import AdminOrderSettings
from src.modules.catalogue.domain.entities.bought_item import BoughtItem
from src.modules.catalogue.domain.value_objects.bought_item_status import BoughtItemCatalogueStatus
from src.modules.catalogue.domain.value_objects.data_source import DataSource
from src.modules.external_data.adapters.outbound.persistence.repositories.pdm_file_snapshot_repository import (
    SqlAlchemyPdmFileSnapshotRepository,
)
from src.modules.external_data.domain.entities.pdm_file_snapshot import PdmFileSnapshot
from src.modules.external_data.domain.value_objects.pdm_file_sync_state import PdmFileSyncState
from src.modules.platform.adapters.outbound.persistence.repositories.pat_repository import (
    SqlAlchemyPatRepository,
)
from src.modules.platform.adapters.outbound.persistence.unit_of_work import SqlAlchemyUnitOfWork
from src.modules.platform.application.dto.pat_dto import CreatePatCommand
from src.modules.platform.application.use_cases.pat.create_pat import CreatePat
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.value_objects.permission import Permission

_URL = "/api/v1/pat/pdm/validate"
PATTERN = r"CAD-\d+"


async def _seed_pdm_enabled(db: AsyncSession) -> None:
    """Enables and configures the integration, and creates the
    order-settings row (see test_api_key_pdm_validate.py's _seed_pdm for
    why that row needs its own explicit seed)."""
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
    await repo.save_made_items(
        dataclasses.replace(await repo.get_made_items(), pdm_part_number_pattern=PATTERN)
    )
    await db.commit()
    current = await repo.get_pdm()
    await repo.save_pdm(
        dataclasses.replace(
            current,
            enabled=True,
            base_url="http://pdm-host:65453",
            vault_name="MyVault",
            username="svc-account",
            password="secret",
            # The stored default also requires `material` and a fabrication
            # step; these tests are about the verdict shape, not the
            # required-field rule (test_validate_pdm_payload.py covers that),
            # so only the locked set is left in play.
            required_fields={"made": [], "bought": []},
        )
    )
    await db.commit()


async def _seed_pdm_enabled_with_vault_id(db: AsyncSession, vault_id: str = "V1") -> None:
    """Same as _seed_pdm_enabled, plus a resolved vault_id, needed for
    file_path -> snapshot resolution, which compares the caller's
    document path against snapshot rows of this exact vault_id."""
    await _seed_pdm_enabled(db)
    repo = SqlAlchemyAdminSettingsRepository(db)
    await repo.save_pdm(dataclasses.replace(await repo.get_pdm(), vault_id=vault_id))
    await db.commit()


async def _seed_snapshot(
    db: AsyncSession, *, vault_id: str = "V1", file_id: int = 100, path: str
) -> None:
    now = datetime(2026, 9, 8, 12, 0, tzinfo=UTC)
    await SqlAlchemyPdmFileSnapshotRepository(db).upsert_many(
        [
            PdmFileSnapshot(
                id=0,
                vault_id=vault_id,
                file_id=file_id,
                kind="made",
                name=path.rsplit("\\", 1)[-1],
                path=path,
                parent_folder_id=1,
                version=1,
                state_id=10,
                state="Released",
                modified_at=None,
                first_seen_at=now,
                last_seen_at=now,
                last_ingested_version=None,
                sync_state=PdmFileSyncState.PENDING,
                last_error=None,
                part_number=None,
                revision=None,
                item_id=None,
                parked_payload=None,
            )
        ]
    )


@pytest.fixture
async def pat_owner(create_user) -> User:
    return await create_user(
        username="pat-owner-pdm-validate",
        email="pat-owner-pdm-validate@example.com",
        permissions=[Permission.WRITE_PAT],
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
            cmd=CreatePatCommand(name="sw-addin-pat", permissions=permissions),
        )
        return result.token

    return _mint


class TestAuth:
    async def test_missing_credential_is_rejected(self, client: httpx.AsyncClient) -> None:
        resp = await client.post(_URL, json={"variables": {}})
        assert resp.status_code == 401


class TestNotEnabled:
    async def test_unconfigured_integration_is_409(
        self, client: httpx.AsyncClient, mint_pat: Callable[[list[str]], Awaitable[str]]
    ) -> None:
        # No _seed_pdm_enabled call: the autouse bare row is disabled.
        token = await mint_pat([])

        resp = await client.post(
            _URL,
            json={"kind": "made", "variables": {}},
            headers={"X-Api-Key": token},
        )

        assert resp.status_code == 409


class TestHappyPath:
    async def test_made_create_verdict_no_extra_permission_needed(
        self,
        db: AsyncSession,
        client: httpx.AsyncClient,
        mint_pat: Callable[[list[str]], Awaitable[str]],
    ) -> None:
        """An empty-scope PAT still gets 200, same posture as the
        field-mapping endpoint (see settings.py's own docstring)."""
        await _seed_pdm_enabled(db)
        token = await mint_pat([])

        resp = await client.post(
            _URL,
            json={
                "kind": "made",
                "file_name": "part.sldprt",
                "variables": {
                    "PDM.PartNumber": "CAD-1001",
                    "PDM.Revision": "A",
                    # article_name is locked-required, never configurable off.
                    "Glados.ArticleName": "Bracket",
                },
            },
            headers={"X-Api-Key": token},
        )

        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body == {
            "ok": True,
            "reasons": [],
            "pending_pdm": [],
            "kind": "made",
            "part_number": "CAD-1001",
            "revision": "A",
            "would": "created",
            "file_identity": "unresolved",
            "notes": [],
        }

    async def test_kind_resolved_from_glados_kind_variable(
        self,
        db: AsyncSession,
        client: httpx.AsyncClient,
        mint_pat: Callable[[list[str]], Awaitable[str]],
    ) -> None:
        await _seed_pdm_enabled(db)
        token = await mint_pat([])

        resp = await client.post(
            _URL,
            json={
                "variables": {
                    "PDM.PartNumber": "CAD-1001",
                    "PDM.Revision": "A",
                    "Glados.Kind": "made",
                }
            },
            headers={"X-Api-Key": token},
        )

        assert resp.status_code == 200, resp.text
        assert resp.json()["kind"] == "made"

    async def test_reports_reasons_without_failing_the_request(
        self,
        db: AsyncSession,
        client: httpx.AsyncClient,
        mint_pat: Callable[[list[str]], Awaitable[str]],
    ) -> None:
        # Changed (pre-release semantics): part_number/revision are
        # PDM-owned, so with nothing on the card at all they land in
        # `pending_pdm` and `would` predicts "created" (no part number
        # yet) rather than being forced to "unknown"; `ok` is still false
        # here only because article_name (engineer-owned, locked) is also
        # missing.
        await _seed_pdm_enabled(db)
        token = await mint_pat([])

        resp = await client.post(
            _URL,
            json={"kind": "made", "variables": {}},
            headers={"X-Api-Key": token},
        )

        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["ok"] is False
        assert "identity variables missing" not in body["reasons"]
        assert body["reasons"] == ["required fields missing: article_name"]
        assert body["pending_pdm"] == ["part_number", "revision"]
        assert body["would"] == "created"

    async def test_wrong_extension_is_a_reason(
        self,
        db: AsyncSession,
        client: httpx.AsyncClient,
        mint_pat: Callable[[list[str]], Awaitable[str]],
    ) -> None:
        await _seed_pdm_enabled(db)
        token = await mint_pat([])

        resp = await client.post(
            _URL,
            json={
                "kind": "made",
                "file_name": "part.sldasm",
                "variables": {"PDM.PartNumber": "CAD-1001", "PDM.Revision": "A"},
            },
            headers={"X-Api-Key": token},
        )

        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert "sldasm files are not made items" in body["reasons"]


class TestValidation:
    async def test_invalid_kind_literal_is_422(
        self,
        db: AsyncSession,
        client: httpx.AsyncClient,
        mint_pat: Callable[[list[str]], Awaitable[str]],
    ) -> None:
        await _seed_pdm_enabled(db)
        token = await mint_pat([])

        resp = await client.post(
            _URL,
            json={"kind": "nonsense", "variables": {}},
            headers={"X-Api-Key": token},
        )

        assert resp.status_code == 422


class TestFileIdentity:
    """the add-in's own document path lets the PAT
    surface resolve a real PDM file identity via the snapshot table, the
    same way the API-key surface already gets one handed to it."""

    async def test_resolved_from_matching_file_path(
        self,
        db: AsyncSession,
        client: httpx.AsyncClient,
        mint_pat: Callable[[list[str]], Awaitable[str]],
    ) -> None:
        await _seed_pdm_enabled_with_vault_id(db)
        await _seed_snapshot(db, file_id=100, path="\\Made-Parts\\CAD-1001.sldprt")
        token = await mint_pat([])

        resp = await client.post(
            _URL,
            json={
                "kind": "made",
                "file_path": "C:\\DEMO-VAULT\\Made-Parts\\CAD-1001.sldprt",
                "variables": {
                    "PDM.PartNumber": "CAD-1001",
                    "PDM.Revision": "A",
                    "Glados.ArticleName": "Bracket",
                },
            },
            headers={"X-Api-Key": token},
        )

        assert resp.status_code == 200, resp.text
        assert resp.json()["file_identity"] == "resolved"

    async def test_unresolved_when_file_path_matches_nothing(
        self,
        db: AsyncSession,
        client: httpx.AsyncClient,
        mint_pat: Callable[[list[str]], Awaitable[str]],
    ) -> None:
        await _seed_pdm_enabled_with_vault_id(db)
        token = await mint_pat([])

        resp = await client.post(
            _URL,
            json={
                "kind": "made",
                "file_path": "C:\\DEMO-VAULT\\Made-Parts\\unknown.sldprt",
                "variables": {
                    "PDM.PartNumber": "CAD-1001",
                    "PDM.Revision": "A",
                    "Glados.ArticleName": "Bracket",
                },
            },
            headers={"X-Api-Key": token},
        )

        assert resp.status_code == 200, resp.text
        assert resp.json()["file_identity"] == "unresolved"

    async def test_unresolved_identity_never_reports_linked_to_another_file(
        self,
        db: AsyncSession,
        client: httpx.AsyncClient,
        mint_pat: Callable[[list[str]], Awaitable[str]],
    ) -> None:
        """The bought counterpart of the same fix: without a resolvable
        file identity, an existing PDM-linked row comes back as an
        in-place update with a note, never a guessed "linked to another
        PDM file"."""
        await _seed_pdm_enabled(db)
        await SqlAlchemyBoughtItemRepository(db).save(
            BoughtItem(
                id=0,
                created=datetime(2026, 1, 1, tzinfo=UTC),
                changed=datetime(2026, 1, 1, tzinfo=UTC),
                changes=[],
                archived=False,
                article_name="Bolt M6",
                order_code_1="OC-1",
                order_code_2=None,
                gtin=None,
                ean=None,
                tariff_number=None,
                status=BoughtItemCatalogueStatus.ACTIVE,
                data_source=DataSource.CAD,
                part_number="CAD-2001",
                mass=None,
                note=None,
                weblink=None,
                files=[],
                creator_id=1,
                approver_id=None,
                manufacturer_id=1,
                article_group_ids=[],
                successor_item_id=None,
                vault_id="V1",
                pdm_file_id=999,
                pdm_file_version=1,
            )
        )
        token = await mint_pat([])

        resp = await client.post(
            _URL,
            json={
                "kind": "bought",
                "variables": {
                    "PDM.PartNumber": "CAD-2001",
                    "Glados.ArticleName": "Bolt M6",
                    "Glados.OrderCode1": "OC-1",
                    "Glados.ManufacturerId": "1",
                },
            },
            headers={"X-Api-Key": token},
        )

        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert not any("linked to another" in r for r in body["reasons"])
        assert body["would"] == "updated"
        assert body["file_identity"] == "unresolved"
        assert "PDM file identity could not be resolved from the document path" in body["notes"]
