"""
HTTP-level coverage of /api/v1/web/made-items.
"""

import dataclasses
from datetime import UTC
from datetime import datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from src.bootstrap.adapters.outbound.persistence.repositories.admin_settings_repository import (
    SqlAlchemyAdminSettingsRepository,
)
from src.modules.catalogue.adapters.outbound.persistence.repositories.fabrication_method_repository import (
    SqlAlchemyFabricationMethodRepository,
)
from src.modules.catalogue.adapters.outbound.persistence.repositories.made_item_repository.item import (
    SqlAlchemyMadeItemRepository,
)
from src.modules.catalogue.domain.entities.admin_settings.made_items import AdminMadeItemSettings
from src.modules.catalogue.domain.entities.fabrication_method import FabricationMethod
from src.modules.catalogue.domain.entities.made_item import MadeItem
from src.modules.catalogue.domain.policies.item_field_ownership import default_policy
from src.modules.catalogue.domain.value_objects.data_source import DataSource
from src.modules.catalogue.domain.value_objects.made_item_status import MadeItemCatalogueStatus
from src.modules.catalogue.domain.value_objects.pdm_sync_state import PdmSyncState
from src.modules.platform.adapters.outbound.persistence.session import SessionLocal
from src.modules.platform.domain.value_objects.localized_text import LocalizedText
from src.modules.platform.domain.value_objects.permission import Permission
from tests.integration._edit_versions import row_version


@pytest.fixture(autouse=True)
async def _seed_made_item_settings(db: Session) -> None:
    """CreateMadeItem reads the made-items numbering domain
    (item_number_format etc.); `_seed_admin_settings` (conftest.py) does not
    cover it. Mirrors InitDatabase's own seed values."""
    await SqlAlchemyAdminSettingsRepository(db).save_made_items(
        AdminMadeItemSettings(
            id=1,
            item_number_format="FAB-{yy}-{seq:05d}",
            lot_number_format="LOT-{yy}-{seq:05d}",
            part_number_auto=True,
            part_number_editable=False,
            revision_start="0",
            revision_separator=":",
            revision_skip_ambiguous_letters=False,
            revision_only_newest_editable=True,
            revision_predecessor_status_web="ask",
            revision_predecessor_status_pdm="replaced",
            revision_field_policy=default_policy(),
            web_creation_allowed=True,
            pdm_part_number_pattern="",
        )
    )
    await db.commit()


async def _create(client: TestClient, **overrides: object) -> dict:
    body = {"revision": "A", "article_name": "Bracket"} | overrides
    resp = await client.post("/api/v1/web/made-items/", json=body)
    assert resp.status_code == 201, resp.text
    return resp.json()


async def test_create_made_item_requires_write_permission(auth_client) -> None:
    client: TestClient = await auth_client(permissions=[])
    resp = await client.post("/api/v1/web/made-items/", json={"revision": "A", "article_name": "X"})
    assert resp.status_code == 403


async def test_create_made_item_rejects_missing_article_name(auth_client) -> None:
    client: TestClient = await auth_client(permissions=["write:made_items"])
    resp = await client.post("/api/v1/web/made-items/", json={"revision": "A"})
    assert resp.status_code == 422


@pytest.mark.smoke
async def test_create_and_read_made_item(auth_client) -> None:
    client: TestClient = await auth_client(permissions=["write:made_items"])
    created = await _create(client)
    resp = await client.get(f"/api/v1/web/made-items/{created['id']}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["article_name"] == "Bracket"
    # WEB-created rows carry no PDM link: all five fields null.
    assert body["vault_id"] is None
    assert body["pdm_file_id"] is None
    assert body["pdm_file_version"] is None
    assert body["pdm_synced_at"] is None
    assert body["pdm_sync_state"] is None


async def test_read_made_item_returns_pdm_link_fields(auth_client, db: Session) -> None:
    """A row ingested from PDM (link columns populated by the repository,
    same shape IngestPdmFile writes) comes back with those fields on the
    web response, proving the mapper/schema wiring, not just the entity."""
    client: TestClient = await auth_client(permissions=[])
    saved = await SqlAlchemyMadeItemRepository(db).save(
        MadeItem(
            id=0,
            created=datetime(2026, 1, 1, tzinfo=UTC),
            changed=datetime(2026, 1, 1, tzinfo=UTC),
            changes=[],
            archived=False,
            revision="A",
            revision_date=None,
            revision_note=None,
            article_name="CAD Bracket",
            status=MadeItemCatalogueStatus.ACTIVE,
            data_source=DataSource.CAD,
            part_number="PN-CAD-1",
            material=None,
            mass=None,
            base_size=None,
            note=None,
            weblink=None,
            files=[],
            creator_id=1,
            approver_id=None,
            bought_item_id=None,
            source_item_id=None,
            article_group_ids=[],
            successor_item_id=None,
            changed_by_id=None,
            vault_id="VAULT-1",
            pdm_file_id=101,
            pdm_file_version=3,
            pdm_synced_at=datetime(2026, 9, 3, 10, 0, tzinfo=UTC),
            pdm_sync_state=PdmSyncState.SYNCED,
        )
    )
    await db.commit()

    resp = await client.get(f"/api/v1/web/made-items/{saved.id}")

    assert resp.status_code == 200
    body = resp.json()
    assert body["vault_id"] == "VAULT-1"
    assert body["pdm_file_id"] == 101
    assert body["pdm_file_version"] == 3
    assert body["pdm_synced_at"] == "2026-09-03T10:00:00Z"
    assert body["pdm_sync_state"] == "synced"


async def _enable_pdm(db: Session, *, cad_items_read_only: bool = True) -> None:
    repo = SqlAlchemyAdminSettingsRepository(db)
    await repo.save_pdm(
        dataclasses.replace(
            await repo.get_pdm(),
            enabled=True,
            base_url="http://pdm-host:65453",
            vault_name="MyVault",
            username="svc-account",
            password="secret",
            cad_items_read_only=cad_items_read_only,
        )
    )
    await db.commit()


class TestPdmLockedFieldsOnGet:
    """pdm_locked_fields on the web GET response, computed
    from the current PDM settings and the requesting actor."""

    async def test_web_row_is_never_locked(self, auth_client, db: Session) -> None:
        await _enable_pdm(db)
        client: TestClient = await auth_client(permissions=["write:made_items"])
        created = await _create(client)

        resp = await client.get(f"/api/v1/web/made-items/{created['id']}")

        assert resp.status_code == 200
        assert resp.json()["pdm_locked_fields"] == []

    async def test_cad_row_is_locked_when_enforced(self, auth_client, db: Session) -> None:
        await _enable_pdm(db)
        client: TestClient = await auth_client(permissions=[])
        saved = await SqlAlchemyMadeItemRepository(db).save(
            MadeItem(
                id=0,
                created=datetime(2026, 1, 1, tzinfo=UTC),
                changed=datetime(2026, 1, 1, tzinfo=UTC),
                changes=[],
                archived=False,
                revision="A",
                revision_date=None,
                revision_note=None,
                article_name="CAD Bracket",
                status=MadeItemCatalogueStatus.ACTIVE,
                data_source=DataSource.CAD,
                part_number="PN-CAD-2",
                material=None,
                mass=None,
                base_size=None,
                note=None,
                weblink=None,
                files=[],
                creator_id=1,
                approver_id=None,
                bought_item_id=None,
                source_item_id=None,
                article_group_ids=[],
                successor_item_id=None,
                changed_by_id=None,
                vault_id="VAULT-1",
                pdm_file_id=102,
                pdm_file_version=1,
            )
        )
        await db.commit()

        resp = await client.get(f"/api/v1/web/made-items/{saved.id}")

        assert resp.status_code == 200
        locked = resp.json()["pdm_locked_fields"]
        assert "part_number" in locked
        assert "article_name" in locked
        # Lifecycle status feature: status is PDM-owned too.
        assert "status" in locked
        assert "successor_item_id" not in locked

    async def test_cad_row_is_not_locked_when_override_off(self, auth_client, db: Session) -> None:
        await _enable_pdm(db, cad_items_read_only=False)
        client: TestClient = await auth_client(permissions=[])
        saved = await SqlAlchemyMadeItemRepository(db).save(
            MadeItem(
                id=0,
                created=datetime(2026, 1, 1, tzinfo=UTC),
                changed=datetime(2026, 1, 1, tzinfo=UTC),
                changes=[],
                archived=False,
                revision="A",
                revision_date=None,
                revision_note=None,
                article_name="CAD Bracket",
                status=MadeItemCatalogueStatus.ACTIVE,
                data_source=DataSource.CAD,
                part_number="PN-CAD-3",
                material=None,
                mass=None,
                base_size=None,
                note=None,
                weblink=None,
                files=[],
                creator_id=1,
                approver_id=None,
                bought_item_id=None,
                source_item_id=None,
                article_group_ids=[],
                successor_item_id=None,
                changed_by_id=None,
                vault_id="VAULT-1",
                pdm_file_id=103,
                pdm_file_version=1,
            )
        )
        await db.commit()

        resp = await client.get(f"/api/v1/web/made-items/{saved.id}")

        assert resp.status_code == 200
        assert resp.json()["pdm_locked_fields"] == []


async def _seed_cad_made_item(
    db: Session,
    *,
    status: MadeItemCatalogueStatus = MadeItemCatalogueStatus.ACTIVE,
    pdm_file_id: int,
    successor_item_id: int | None = None,
) -> MadeItem:
    seeded = await SqlAlchemyMadeItemRepository(db).save(
        MadeItem(
            id=0,
            created=datetime(2026, 1, 1, tzinfo=UTC),
            changed=datetime(2026, 1, 1, tzinfo=UTC),
            changes=[],
            archived=False,
            revision="A",
            revision_date=None,
            revision_note=None,
            article_name="CAD Bracket",
            status=status,
            data_source=DataSource.CAD,
            part_number=f"PN-CAD-{pdm_file_id}",
            material=None,
            mass=None,
            base_size=None,
            note=None,
            weblink=None,
            files=[],
            creator_id=1,
            approver_id=None,
            bought_item_id=None,
            source_item_id=None,
            article_group_ids=[],
            successor_item_id=successor_item_id,
            changed_by_id=None,
            vault_id="VAULT-1",
            pdm_file_id=pdm_file_id,
            pdm_file_version=1,
        )
    )
    await db.commit()
    return seeded


class TestPdmSuccessorRequiresReplacedStatus:
    """Lifecycle status feature (docs/PDM_INTEGRATION.md's "lifecycle
    mapping" section): status is PDM-owned and locked on a CAD row while
    enforcement is active; successor_item_id may still be assigned there,
    but only once the row's own status is already `replaced`."""

    async def test_status_change_is_rejected(self, auth_client, db: Session) -> None:
        await _enable_pdm(db)
        client: TestClient = await auth_client(permissions=["write:made_items"])
        item = await _seed_cad_made_item(db, status=MadeItemCatalogueStatus.ACTIVE, pdm_file_id=501)

        resp = await client.put(
            f"/api/v1/web/made-items/{item.id}",
            json={
                "expected_edit_version": await row_version(
                    client, f"/api/v1/web/made-items/{item.id}"
                ),
                "article_name": "CAD Bracket",
                "part_number": item.part_number,
                "status": "inactive",
            },
        )

        assert resp.status_code == 409
        assert resp.json()["code"] == "PdmOwnedFieldReadOnlyError"

    async def test_successor_rejected_when_status_is_not_replaced(
        self, auth_client, db: Session
    ) -> None:
        await _enable_pdm(db)
        client: TestClient = await auth_client(permissions=["write:made_items"])
        item = await _seed_cad_made_item(db, status=MadeItemCatalogueStatus.ACTIVE, pdm_file_id=502)

        resp = await client.put(
            f"/api/v1/web/made-items/{item.id}",
            json={
                "expected_edit_version": await row_version(
                    client, f"/api/v1/web/made-items/{item.id}"
                ),
                "article_name": "CAD Bracket",
                "part_number": item.part_number,
                "status": "active",
                "successor_item_id": item.id,
            },
        )

        assert resp.status_code == 409
        assert resp.json()["code"] == "PdmSuccessorRequiresReplacedStatusError"

    async def test_successor_allowed_when_status_is_replaced(
        self, auth_client, db: Session
    ) -> None:
        await _enable_pdm(db)
        client: TestClient = await auth_client(permissions=["write:made_items"])
        item = await _seed_cad_made_item(
            db, status=MadeItemCatalogueStatus.REPLACED, pdm_file_id=503
        )
        successor = await _seed_cad_made_item(
            db, status=MadeItemCatalogueStatus.ACTIVE, pdm_file_id=504
        )

        resp = await client.put(
            f"/api/v1/web/made-items/{item.id}",
            json={
                "expected_edit_version": await row_version(
                    client, f"/api/v1/web/made-items/{item.id}"
                ),
                "article_name": "CAD Bracket",
                "part_number": item.part_number,
                "status": "replaced",
                "successor_item_id": successor.id,
            },
        )

        assert resp.status_code == 200, resp.text
        assert resp.json()["successor_item_id"] == successor.id

    async def test_clearing_successor_never_requires_replaced_status(
        self, auth_client, db: Session
    ) -> None:
        await _enable_pdm(db)
        client: TestClient = await auth_client(permissions=["write:made_items"])
        item = await _seed_cad_made_item(
            db, status=MadeItemCatalogueStatus.REPLACED, pdm_file_id=505, successor_item_id=999
        )

        resp = await client.put(
            f"/api/v1/web/made-items/{item.id}",
            json={
                "expected_edit_version": await row_version(
                    client, f"/api/v1/web/made-items/{item.id}"
                ),
                "article_name": "CAD Bracket",
                "part_number": item.part_number,
                "status": "replaced",
                "successor_item_id": None,
            },
        )

        assert resp.status_code == 200, resp.text
        assert resp.json()["successor_item_id"] is None


async def test_read_missing_made_item_404(auth_client) -> None:
    client: TestClient = await auth_client(permissions=[])
    resp = await client.get("/api/v1/web/made-items/999999")
    assert resp.status_code == 404


async def test_list_made_items(auth_client) -> None:
    client: TestClient = await auth_client(permissions=["write:made_items"])
    await _create(client)
    resp = await client.get("/api/v1/web/made-items/")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] >= 1


async def test_two_auto_numbered_creates_get_distinct_part_numbers(auth_client) -> None:
    # CreateMadeItem claims through IPartNumberRegistry.claim(), so the
    # registry is what the second create's next_part_number() sees, and
    # two back-to-back auto-numbered creates get distinct part numbers.
    client: TestClient = await auth_client(permissions=["write:made_items"])
    first = await _create(client)
    second = await _create(client)
    assert first["part_number"] is not None
    assert second["part_number"] is not None
    assert first["part_number"] != second["part_number"]


async def test_update_made_item_requires_write_permission(auth_client) -> None:
    creator: TestClient = await auth_client(
        username="creator", email="creator@example.com", permissions=["write:made_items"]
    )
    created = await _create(creator)
    reader: TestClient = await auth_client(
        username="reader", email="reader@example.com", permissions=[]
    )
    resp = await reader.put(
        f"/api/v1/web/made-items/{created['id']}",
        json={
            "expected_edit_version": created["edit_version"],
            "article_name": "Bracket",
            "status": "active",
        },
    )
    assert resp.status_code == 403


async def test_update_made_item(auth_client) -> None:
    # revision is immutable in place: PUT does not accept it (and
    # would ignore it if sent); the row's revision stays whatever it was
    # created with. weblink (not article_name) is edited here because it
    # is not a revision-policy field on a WEB item, while article_name is,
    # and changing it in place would 409.
    client: TestClient = await auth_client(permissions=["write:made_items"])
    created = await _create(client)
    resp = await client.put(
        f"/api/v1/web/made-items/{created['id']}",
        # part_number_editable is False (seeded settings): round-trip the
        # auto-generated part number unchanged, or the use case reads the
        # omitted field as an edit attempt and 409s.
        json={
            "expected_edit_version": created["edit_version"],
            "article_name": "Bracket",
            "weblink": "https://example.com",
            "part_number": created["part_number"],
            "status": created["status"],
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["weblink"] == "https://example.com"
    assert body["revision"] == created["revision"]


async def test_archive_made_item_requires_delete_permission(auth_client) -> None:
    creator: TestClient = await auth_client(
        username="creator", email="creator@example.com", permissions=["write:made_items"]
    )
    created = await _create(creator)
    resp = await creator.post(f"/api/v1/web/made-items/{created['id']}/archive")
    assert resp.status_code == 403


async def test_archive_made_item(auth_client) -> None:
    creator: TestClient = await auth_client(
        username="creator", email="creator@example.com", permissions=["write:made_items"]
    )
    created = await _create(creator)
    archiver: TestClient = await auth_client(
        username="archiver", email="archiver@example.com", permissions=["delete:made_items"]
    )
    resp = await archiver.post(f"/api/v1/web/made-items/{created['id']}/archive")
    assert resp.status_code == 200
    assert resp.json()["archived"] is True


async def test_archived_made_item_hidden_from_default_list_but_resolves_by_id(auth_client) -> None:
    client: TestClient = await auth_client(permissions=["write:made_items", "delete:made_items"])
    created = await _create(client)

    await client.post(f"/api/v1/web/made-items/{created['id']}/archive")

    default_list = (await client.get("/api/v1/web/made-items/")).json()
    assert created["id"] not in {i["id"] for i in default_list["items"]}

    by_id = await client.get(f"/api/v1/web/made-items/{created['id']}")
    assert by_id.status_code == 200
    assert by_id.json()["archived"] is True


async def test_restore_made_item(auth_client) -> None:
    client: TestClient = await auth_client(permissions=["write:made_items", "delete:made_items"])
    created = await _create(client)
    await client.post(f"/api/v1/web/made-items/{created['id']}/archive")

    resp = await client.post(f"/api/v1/web/made-items/{created['id']}/restore")
    assert resp.status_code == 200
    assert resp.json()["archived"] is False


async def test_create_made_item_process_requires_data(auth_client) -> None:
    """A quick pass over the routing-step sub-resource: create one process
    then reorder it, exercising a second route on this router beyond plain
    CRUD (A1 leans on this file as its net for the *_files.py siblings,
    but the process sub-resource is this router's own distinguishing
    feature)."""
    client: TestClient = await auth_client(permissions=["write:made_items"])
    created = await _create(client)
    resp = await client.post(
        f"/api/v1/web/made-items/{created['id']}/processes",
        json={"fabrication_method_id": 1},
    )
    # No fabrication method #1 exists in this throwaway DB, so a domain 404,
    # not a schema-validation 422, proves the route + use case resolve.
    assert resp.status_code == 404


async def test_deleting_the_only_process_persists(auth_client, db: Session) -> None:
    """With no steps left there is nothing to re-sequence, so the use case's
    own commit is the only thing that makes the delete durable."""
    client: TestClient = await auth_client(permissions=["write:made_items"])
    created = await _create(client)
    method = await SqlAlchemyFabricationMethodRepository(db).save(
        FabricationMethod(
            id=0,
            created=datetime.now(UTC),
            changed=datetime.now(UTC),
            changes=[],
            archived=False,
            name=LocalizedText({"enGB": "Milling"}),
            label_color="#000000",
            label_font_color="#ffffff",
            description=LocalizedText(),
            creator_id=1,
        )
    )
    await db.commit()
    resp = await client.post(
        f"/api/v1/web/made-items/{created['id']}/processes",
        json={"fabrication_method_id": method.id},
    )
    assert resp.status_code == 201, resp.text
    process_id = resp.json()["id"]

    resp = await client.delete(f"/api/v1/web/made-items/{created['id']}/processes/{process_id}")

    assert resp.status_code == 204
    async with SessionLocal() as session:
        assert await SqlAlchemyMadeItemRepository(session).get_processes(created["id"]) == []


async def test_restore_made_item_is_persisted(auth_client) -> None:
    """Reads the restored item back through a separate request, so a
    restore that is never committed fails here."""
    client: TestClient = await auth_client(permissions=["write:made_items", "delete:made_items"])
    created = await _create(client)
    await client.post(f"/api/v1/web/made-items/{created['id']}/archive")

    resp = await client.post(f"/api/v1/web/made-items/{created['id']}/restore")
    assert resp.status_code == 200

    by_id = await client.get(f"/api/v1/web/made-items/{created['id']}")
    assert by_id.json()["archived"] is False


async def test_process_writes_are_persisted(auth_client, db: Session) -> None:
    """Creates, edits, reorders and regroups routing steps, reading the
    item back through a separate request after every write, so a process
    write that is never committed fails here."""
    client: TestClient = await auth_client(permissions=["write:made_items"])
    created = await _create(client)
    base = f"/api/v1/web/made-items/{created['id']}"
    method = await SqlAlchemyFabricationMethodRepository(db).save(
        FabricationMethod(
            id=0,
            created=datetime.now(UTC),
            changed=datetime.now(UTC),
            changes=[],
            archived=False,
            name=LocalizedText({"enGB": "Turning"}),
            label_color="#000000",
            label_font_color="#ffffff",
            description=LocalizedText(),
            creator_id=1,
        )
    )
    await db.commit()

    async def processes() -> list[dict]:
        resp = await client.get(base)
        assert resp.status_code == 200, resp.text
        return sorted(resp.json()["processes"], key=lambda p: p["position"])

    ids = []
    for _ in range(2):
        resp = await client.post(f"{base}/processes", json={"fabrication_method_id": method.id})
        assert resp.status_code == 201, resp.text
        ids.append(resp.json()["id"])
    assert [p["id"] for p in await processes()] == ids

    resp = await client.put(
        f"{base}/processes/{ids[0]}",
        json={"fabrication_method_id": method.id, "note": "Deburr"},
    )
    assert resp.status_code == 200, resp.text
    assert (await processes())[0]["note"] == "Deburr"

    resp = await client.put(
        f"{base}/processes/reorder", json={"ordered_process_ids": [ids[1], ids[0]]}
    )
    assert resp.status_code == 200, resp.text
    assert [p["id"] for p in await processes()] == [ids[1], ids[0]]

    resp = await client.put(f"{base}/processes/regroup", json={"groups": [[ids[1], ids[0]]]})
    assert resp.status_code == 200, resp.text
    assert {p["group_index"] for p in await processes()} == {0}


class TestCustomerData:
    async def test_writes_and_reads_the_customer_data(self, auth_client) -> None:
        client: TestClient = await auth_client(
            permissions=["write:made_items", Permission.WRITE_PROJECTS]
        )
        customer = await client.post("/api/v1/web/customers/", json={"name": "Customer A"})
        assert customer.status_code == 201, customer.text
        customer_id = customer.json()["id"]

        created = await _create(
            client,
            customer_id=customer_id,
            customer_part_number="C-100",
            customer_revision="B",
        )

        resp = await client.get(f"/api/v1/web/made-items/{created['id']}")
        assert resp.status_code == 200
        body = resp.json()
        assert body["customer_id"] == customer_id
        assert body["customer_name"] == "Customer A"
        assert body["customer_part_number"] == "C-100"
        assert body["customer_revision"] == "B"

        listed = await client.get("/api/v1/web/made-items/", params={"customer_id": customer_id})
        assert [row["id"] for row in listed.json()["items"]] == [created["id"]]

    async def test_customer_part_number_without_customer_is_refused(self, auth_client) -> None:
        client: TestClient = await auth_client(permissions=["write:made_items"])
        resp = await client.post(
            "/api/v1/web/made-items/",
            json={"revision": "A", "article_name": "Housing", "customer_part_number": "C-100"},
        )
        assert resp.status_code == 422
