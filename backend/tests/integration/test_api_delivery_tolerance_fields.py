"""
The delivery tolerances over HTTP: the global pair on the order settings and
an item's own pair on the bought and source item web forms, each refused
outside 0 to 100 percent, and an item update that leaves them out, as a
pat client's does, keeping the item's values.
"""

import pytest
from sqlalchemy.orm import Session

from src.bootstrap.adapters.outbound.persistence.repositories.admin_settings_repository import (
    SqlAlchemyAdminSettingsRepository,
)
from src.modules.catalogue.domain.entities.admin_settings.orders import AdminOrderSettings
from src.modules.platform.adapters.outbound.persistence.repositories.pat_repository import (
    SqlAlchemyPatRepository,
)
from src.modules.platform.adapters.outbound.persistence.unit_of_work import SqlAlchemyUnitOfWork
from src.modules.platform.application.dto.pat_dto import CreatePatCommand
from src.modules.platform.application.use_cases.pat.create_pat import CreatePat
from src.modules.platform.domain.value_objects.permission import Permission
from tests.integration._edit_versions import row_version

ORDERS_SETTINGS = "/api/v1/web/admin/settings/orders"
BOUGHT_ITEMS = "/api/v1/web/bought-items/"
SOURCE_ITEMS = "/api/v1/web/source-items/"


@pytest.fixture(autouse=True)
async def _seed_order_settings(db: Session) -> None:
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


@pytest.fixture
async def client(auth_client):
    return await auth_client(
        permissions=[
            Permission.READ_SETTINGS,
            Permission.WRITE_SETTINGS,
            Permission.WRITE_BOUGHT_ITEMS,
            Permission.WRITE_SUPPLIERS,
            Permission.WRITE_SOURCE_ITEMS,
            Permission.WRITE_SOURCE_ITEM_TYPES,
        ]
    )


async def _supplier(client) -> int:
    resp = await client.post("/api/v1/web/suppliers/", json={"name": "Tolerance AG", "level": "B"})
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


async def _pat_token(db: Session, create_user) -> str:
    owner = await create_user(
        username="pat-owner",
        email="pat-owner@example.com",
        permissions=[Permission.WRITE_PAT, Permission.WRITE_BOUGHT_ITEMS],
    )
    created = await CreatePat(
        SqlAlchemyPatRepository(db),
        settings_repo=SqlAlchemyAdminSettingsRepository(db),
        uow=SqlAlchemyUnitOfWork(db),
    ).execute(
        actor=owner,
        cmd=CreatePatCommand(name="tolerance", permissions=[Permission.WRITE_BOUGHT_ITEMS]),
    )
    return created.token


async def test_the_order_settings_carry_the_global_tolerances(client) -> None:
    assert (await client.get(ORDERS_SETTINGS)).json()["over_delivery_tolerance_percent"] == 0.0

    resp = await client.put(
        ORDERS_SETTINGS,
        json={"over_delivery_tolerance_percent": 5.0, "under_delivery_tolerance_percent": 2.0},
    )
    assert resp.status_code == 200, resp.text
    body = (await client.get(ORDERS_SETTINGS)).json()
    assert body["over_delivery_tolerance_percent"] == 5.0
    assert body["under_delivery_tolerance_percent"] == 2.0


async def test_a_tolerance_outside_the_percent_range_is_refused(client) -> None:
    resp = await client.put(ORDERS_SETTINGS, json={"under_delivery_tolerance_percent": 101.0})
    assert resp.status_code == 422
    assert "under-delivery tolerance" in resp.text


async def test_a_bought_item_keeps_its_tolerances_through_an_update_without_them(
    client, db: Session, create_user
) -> None:
    supplier_id = await _supplier(client)
    created = await client.post(
        BOUGHT_ITEMS,
        json={
            "order_code_1": "TOL-1",
            "article_name": "Toleranced",
            "manufacturer_id": supplier_id,
            "over_delivery_tolerance_percent": 10.0,
        },
    )
    assert created.status_code == 201, created.text
    item = created.json()
    assert item["over_delivery_tolerance_percent"] == 10.0
    assert item["under_delivery_tolerance_percent"] is None

    # The pat request has no tolerance fields, so its update keeps the item's.
    token = await _pat_token(db, create_user)
    pat = await client.put(
        f"/api/v1/pat/bought-items/{item['id']}",
        headers={"X-Api-Key": token},
        json={
            "order_code_1": "TOL-1",
            "article_name": "Renamed",
            "part_number": item["part_number"],
            "manufacturer_id": supplier_id,
            "status": "active",
        },
    )
    assert pat.status_code == 200, pat.text
    assert pat.json()["over_delivery_tolerance_percent"] == 10.0

    updated = await client.put(
        f"{BOUGHT_ITEMS}{item['id']}",
        json={
            "expected_edit_version": await row_version(client, f"{BOUGHT_ITEMS}{item['id']}"),
            "order_code_1": "TOL-1",
            "article_name": "Renamed",
            "part_number": item["part_number"],
            "manufacturer_id": supplier_id,
            "status": "active",
            "over_delivery_tolerance_percent": 10.0,
            "under_delivery_tolerance_percent": 3.0,
        },
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["under_delivery_tolerance_percent"] == 3.0


async def test_an_item_tolerance_outside_the_percent_range_is_refused(client) -> None:
    supplier_id = await _supplier(client)
    resp = await client.post(
        BOUGHT_ITEMS,
        json={
            "order_code_1": "TOL-2",
            "article_name": "Toleranced",
            "manufacturer_id": supplier_id,
            "over_delivery_tolerance_percent": -1.0,
        },
    )
    assert resp.status_code == 422
    assert "over-delivery tolerance" in resp.text


async def test_a_source_item_carries_its_tolerances(client) -> None:
    type_id = (
        await client.post("/api/v1/web/source-item-types/", json={"name": {"enGB": "Sheet"}})
    ).json()["id"]
    created = await client.post(
        SOURCE_ITEMS,
        json={"type_id": type_id, "material": "S235", "under_delivery_tolerance_percent": 5.0},
    )
    assert created.status_code == 201, created.text
    item = created.json()
    assert item["under_delivery_tolerance_percent"] == 5.0

    updated = await client.put(
        f"{SOURCE_ITEMS}{item['id']}",
        json={
            "expected_edit_version": await row_version(client, f"{SOURCE_ITEMS}{item['id']}"),
            "type_id": type_id,
            "material": "S235",
            "status": "active",
            "over_delivery_tolerance_percent": 1.0,
        },
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["over_delivery_tolerance_percent"] == 1.0
    # The web form sends both, and the one it leaves out takes the global value.
    assert updated.json()["under_delivery_tolerance_percent"] is None
