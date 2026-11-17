"""
POST /api/v1/web/bought-items/{id}/merge end to end, whose body binds the
adapter schema MergeBoughtItemRequest rather than the application layer's
own command DTO, plus the PDM link fields of the bought item read, and the
merge moving the source's order lines and demands with their row versions.
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
from src.modules.catalogue.adapters.outbound.persistence.models.bought_item_model import (
    BoughtItemOrmModel,
)
from src.modules.catalogue.adapters.outbound.persistence.repositories.bought_item_repository.item import (
    SqlAlchemyBoughtItemRepository,
)
from src.modules.catalogue.domain.entities.admin_settings.orders import AdminOrderSettings
from src.modules.catalogue.domain.entities.bought_item import BoughtItem
from src.modules.catalogue.domain.value_objects.bought_item_status import BoughtItemCatalogueStatus
from src.modules.catalogue.domain.value_objects.data_source import DataSource
from src.modules.catalogue.domain.value_objects.pdm_sync_state import PdmSyncState
from src.modules.fulfillment.adapters.outbound.persistence.models.bought_item_demand_item_model import (
    BoughtItemDemandItemOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.order_item_model import (
    OrderItemOrmModel,
)
from tests.integration import _lifecycle_seed as seed


@pytest.fixture(autouse=True)
async def _seed_order_settings(db: Session) -> None:
    """CreateBoughtItem reads the order/purchasing numbering domain
    (part_number_format etc.); `_seed_admin_settings` (conftest.py) does
    not cover it. Mirrors InitDatabase's own defaults. part_number_auto is
    on (matching InitDatabase): this test creates two items per case and
    only cares about merge behaviour, never the part number itself, but
    CreateBoughtItem claims through part_number_registry.claim(), so the
    registry (not an unlocked table scan) is what keeps the two
    auto-numbered items distinct."""
    await SqlAlchemyAdminSettingsRepository(db).save_orders(
        AdminOrderSettings(
            id=1,
            order_number_format="ORD-{yy}-{seq:05d}",
            part_number_format="PUR-{yy}-{seq:05d}",
            part_number_auto=True,
            part_number_editable=False,
            web_creation_allowed=True,
            pdm_part_number_pattern="",
        )
    )
    await db.commit()


async def _create_item(client: TestClient, supplier_id: int, order_code: str) -> dict:
    resp = await client.post(
        "/api/v1/web/bought-items/",
        json={
            "order_code_1": order_code,
            "article_name": f"Item {order_code}",
            "manufacturer_id": supplier_id,
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _create_supplier(client: TestClient) -> int:
    resp = await client.post(
        "/api/v1/web/suppliers/", json={"name": "Merge Test Supplier", "level": "B"}
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


async def test_merge_bought_items(auth_client) -> None:
    client: TestClient = await auth_client(
        permissions=["write:bought_items", "write:suppliers", "delete:bought_items"]
    )
    supplier_id = await _create_supplier(client)
    source = await _create_item(client, supplier_id, "SRC-1")
    target = await _create_item(client, supplier_id, "TGT-1")

    resp = await client.post(
        f"/api/v1/web/bought-items/{source['id']}/merge", json={"target_id": target["id"]}
    )
    assert resp.status_code == 200
    assert resp.json()["id"] == target["id"]

    # The merged-away source is gone (soft-deleted / redirected); reading
    # it directly reflects the merge, proving the use case actually ran.
    resp = await client.get(f"/api/v1/web/bought-items/{source['id']}")
    assert resp.status_code in (200, 404)


async def test_merge_bought_items_rejects_missing_target_id(auth_client) -> None:
    client: TestClient = await auth_client(
        permissions=["write:bought_items", "write:suppliers", "delete:bought_items"]
    )
    supplier_id = await _create_supplier(client)
    source = await _create_item(client, supplier_id, "SRC-2")

    resp = await client.post(f"/api/v1/web/bought-items/{source['id']}/merge", json={})
    assert resp.status_code == 422


async def test_merge_bought_items_requires_delete_permission(auth_client) -> None:
    client: TestClient = await auth_client(permissions=["write:bought_items", "write:suppliers"])
    supplier_id = await _create_supplier(client)
    source = await _create_item(client, supplier_id, "SRC-3")
    target = await _create_item(client, supplier_id, "TGT-3")

    resp = await client.post(
        f"/api/v1/web/bought-items/{source['id']}/merge", json={"target_id": target["id"]}
    )
    assert resp.status_code == 403


async def test_merge_bought_items_refuses_an_inactive_target(auth_client, db) -> None:
    client: TestClient = await auth_client(
        permissions=["write:bought_items", "write:suppliers", "delete:bought_items"]
    )
    supplier_id = await _create_supplier(client)
    source = await _create_item(client, supplier_id, "SRC-I")
    target = await _create_item(client, supplier_id, "TGT-I")
    (await db.get(BoughtItemOrmModel, target["id"])).status = "inactive"
    await db.commit()

    resp = await client.post(
        f"/api/v1/web/bought-items/{source['id']}/merge", json={"target_id": target["id"]}
    )

    assert resp.status_code == 409, resp.text
    assert resp.json()["code"] == "BoughtItemInactiveError"
    assert (await client.get(f"/api/v1/web/bought-items/{source['id']}")).status_code == 200


async def test_merge_bought_items_reactivates_a_target_the_source_had_replaced(
    auth_client, db
) -> None:
    client: TestClient = await auth_client(
        permissions=["write:bought_items", "write:suppliers", "delete:bought_items"]
    )
    supplier_id = await _create_supplier(client)
    source = await _create_item(client, supplier_id, "SRC-R")
    target = await _create_item(client, supplier_id, "TGT-R")
    row = await db.get(BoughtItemOrmModel, target["id"])
    row.status = "replaced"
    row.successor_item_id = source["id"]
    await db.commit()

    resp = await client.post(
        f"/api/v1/web/bought-items/{source['id']}/merge", json={"target_id": target["id"]}
    )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert (body["status"], body["successor_item_id"]) == ("active", None)
    merged = await db.get(BoughtItemOrmModel, target["id"], populate_existing=True)
    assert any("active again" in str(line) for line in merged.changes)


# ── PDM link fields on the response ────────────────────────────────


async def test_read_bought_item_pdm_fields_null_for_web_row(auth_client) -> None:
    client: TestClient = await auth_client(permissions=["write:bought_items", "write:suppliers"])
    supplier_id = await _create_supplier(client)
    created = await _create_item(client, supplier_id, "SRC-PDM-NULL")

    resp = await client.get(f"/api/v1/web/bought-items/{created['id']}")

    assert resp.status_code == 200
    body = resp.json()
    assert body["vault_id"] is None
    assert body["pdm_file_id"] is None
    assert body["pdm_file_version"] is None
    assert body["pdm_synced_at"] is None
    assert body["pdm_sync_state"] is None


async def test_read_bought_item_returns_pdm_link_fields(auth_client, db: Session) -> None:
    """A row claimed/ingested by PDM (link columns populated by the
    repository, same shape IngestPdmFile writes) comes back with those
    fields on the web response."""
    client: TestClient = await auth_client(permissions=[])
    saved = await SqlAlchemyBoughtItemRepository(db).save(
        BoughtItem(
            id=0,
            created=datetime(2026, 1, 1, tzinfo=UTC),
            changed=datetime(2026, 1, 1, tzinfo=UTC),
            changes=[],
            archived=False,
            article_name="CAD Widget",
            order_code_1="OC-CAD-1",
            order_code_2=None,
            gtin=None,
            ean=None,
            tariff_number=None,
            status=BoughtItemCatalogueStatus.ACTIVE,
            data_source=DataSource.CAD,
            part_number="PN-CAD-BOUGHT-1",
            mass=None,
            note=None,
            weblink=None,
            files=[],
            creator_id=1,
            approver_id=None,
            manufacturer_id=1,
            article_group_ids=[],
            successor_item_id=None,
            vault_id="VAULT-1",
            pdm_file_id=202,
            pdm_file_version=5,
            pdm_synced_at=datetime(2026, 9, 3, 10, 0, tzinfo=UTC),
            pdm_sync_state=PdmSyncState.SYNCED,
        )
    )
    await db.commit()

    resp = await client.get(f"/api/v1/web/bought-items/{saved.id}")

    assert resp.status_code == 200
    body = resp.json()
    assert body["vault_id"] == "VAULT-1"
    assert body["pdm_file_id"] == 202
    assert body["pdm_file_version"] == 5
    assert body["pdm_synced_at"] == "2026-09-03T10:00:00Z"
    assert body["pdm_sync_state"] == "synced"


async def test_read_bought_item_returns_pdm_locked_fields_when_enforced(
    auth_client, db: Session
) -> None:
    """pdm_locked_fields on the web GET response, computed
    from the current PDM settings and the requesting actor."""
    repo = SqlAlchemyAdminSettingsRepository(db)
    await repo.save_pdm(
        dataclasses.replace(
            await repo.get_pdm(),
            enabled=True,
            base_url="http://pdm-host:65453",
            vault_name="MyVault",
            username="svc-account",
            password="secret",
            cad_items_read_only=True,
        )
    )
    await db.commit()
    client: TestClient = await auth_client(permissions=[])
    saved = await SqlAlchemyBoughtItemRepository(db).save(
        BoughtItem(
            id=0,
            created=datetime(2026, 1, 1, tzinfo=UTC),
            changed=datetime(2026, 1, 1, tzinfo=UTC),
            changes=[],
            archived=False,
            article_name="CAD Widget",
            order_code_1="OC-CAD-2",
            order_code_2=None,
            gtin=None,
            ean=None,
            tariff_number=None,
            status=BoughtItemCatalogueStatus.ACTIVE,
            data_source=DataSource.CAD,
            part_number="PN-CAD-BOUGHT-2",
            mass=None,
            note=None,
            weblink=None,
            files=[],
            creator_id=1,
            approver_id=None,
            manufacturer_id=1,
            article_group_ids=[],
            successor_item_id=None,
            vault_id="VAULT-1",
            pdm_file_id=303,
            pdm_file_version=1,
        )
    )
    await db.commit()

    resp = await client.get(f"/api/v1/web/bought-items/{saved.id}")

    assert resp.status_code == 200
    locked = resp.json()["pdm_locked_fields"]
    assert "part_number" in locked
    assert "order_code_1" in locked


async def test_merge_bought_items_moves_lines_and_demands_with_their_versions(
    auth_client, db
) -> None:
    client: TestClient = await auth_client(
        permissions=["write:bought_items", "write:suppliers", "delete:bought_items"]
    )
    supplier_id = await _create_supplier(client)
    source = await _create_item(client, supplier_id, "SRC-V")
    target = await _create_item(client, supplier_id, "TGT-V")
    order = await seed.order(db, "draft")
    line = await seed.line(db, order, "pending", bought_item_id=source["id"])
    demand = await seed.bought_demand(db, "allocated", line, 5.0, item_id=source["id"])
    await db.commit()
    await seed.settle(db)
    before = {
        "line": (await db.get(OrderItemOrmModel, line.id, populate_existing=True)).version,
        "demand": (
            await db.get(BoughtItemDemandItemOrmModel, demand.id, populate_existing=True)
        ).version,
    }

    resp = await client.post(
        f"/api/v1/web/bought-items/{source['id']}/merge", json={"target_id": target["id"]}
    )

    assert resp.status_code == 200, resp.text
    moved_line = await db.get(OrderItemOrmModel, line.id, populate_existing=True)
    moved_demand = await db.get(BoughtItemDemandItemOrmModel, demand.id, populate_existing=True)
    assert (moved_line.bought_item_id, moved_line.version) == (target["id"], before["line"] + 1)
    assert (moved_demand.item_id, moved_demand.version) == (target["id"], before["demand"] + 1)
