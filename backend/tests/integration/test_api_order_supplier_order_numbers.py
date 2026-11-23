"""
Supplier order numbers of an order over HTTP: a save replaces the whole list,
normalised, and moves the order's edit version; a user with only write:orders
may change them on an ordered order and is offered the action; a canceled
order refuses them; an older edit version answers 409 and an oversized list
422; the orders list's number filter, the order pickers' search and the
global search find an order by any of its numbers, umlauts included.
"""

from datetime import UTC
from datetime import datetime
from typing import Any

import pytest

from src.modules.platform.const import API_WEB
from src.modules.platform.domain.value_objects.permission import Permission
from src.modules.workspace.adapters.outbound.persistence.repositories.project_repository import (
    SqlAlchemyProjectRepository,
)
from src.modules.workspace.domain.entities.project import Project
from tests.integration._edit_versions import order_version
from tests.integration._suppliers import seed_supplier

ORDERS = f"{API_WEB}/orders"
SEARCH = f"{API_WEB}/search/"
ACTION = "edit_supplier_order_numbers"


@pytest.fixture(autouse=True)
async def _supplier(db) -> None:
    await seed_supplier(db)


@pytest.fixture
async def manager(db, auth_client) -> Any:
    client = await auth_client(permissions=[Permission.WRITE_ORDERS, Permission.MANAGE_ORDERS])
    project = await SqlAlchemyProjectRepository(db).save(
        Project(id=0, created=datetime.now(UTC), creator_id=1, project_number="P-411")
    )
    await db.commit()
    client.project_id = project.id
    return client


@pytest.fixture
async def writer(auth_client) -> Any:
    return await auth_client(
        permissions=[Permission.WRITE_ORDERS], username="writer", email="writer@example.com"
    )


async def _ordered_order(manager: Any) -> int:
    order = await manager.post(f"{ORDERS}/", json={"supplier_id": 1})
    order_id = int(order.json()["id"])
    added = await manager.post(
        f"{ORDERS}/{order_id}/items",
        json={
            "order_id": order_id,
            "supplier_id": 1,
            "project_id": manager.project_id,
            "virtual_name": "Bracket",
            "quantity": 4,
            "unit": "pcs",
        },
    )
    assert added.status_code == 201, added.text
    submitted = await manager.put(f"{ORDERS}/{order_id}/submit")
    assert submitted.status_code == 200, submitted.text
    assert submitted.json()["status"] == "ordered"
    return order_id


async def _set(client: Any, order_id: int, numbers: list[str]) -> Any:
    version = await order_version(client, order_id)
    return await client.put(
        f"{ORDERS}/{order_id}/supplier-order-numbers",
        json={"numbers": numbers, "expected_edit_version": version},
    )


async def test_numbers_are_saved_normalised_and_read_back(manager) -> None:
    order_id = await _ordered_order(manager)
    before = await order_version(manager, order_id)

    saved = await _set(manager, order_id, [" AB-24117 ", "", "AB-24131", "ab-24117"])

    assert saved.status_code == 200, saved.text
    assert saved.json()["supplier_order_numbers"] == ["AB-24117", "AB-24131"]
    assert saved.json()["edit_version"] == before + 1
    read = (await manager.get(f"{ORDERS}/{order_id}")).json()
    assert read["supplier_order_numbers"] == ["AB-24117", "AB-24131"]


async def test_a_new_order_has_no_numbers(manager) -> None:
    created = await manager.post(f"{ORDERS}/", json={"supplier_id": 1})

    assert created.json()["supplier_order_numbers"] == []


async def test_a_user_with_only_write_orders_edits_an_ordered_order(manager, writer) -> None:
    order_id = await _ordered_order(manager)

    read = (await writer.get(f"{ORDERS}/{order_id}")).json()
    assert ACTION in read["actions"]
    assert "edit" not in read["actions"]

    saved = await _set(writer, order_id, ["AB-1"])

    assert saved.status_code == 200, saved.text
    assert saved.json()["supplier_order_numbers"] == ["AB-1"]


async def test_a_canceled_order_refuses_the_numbers(manager) -> None:
    order_id = await _ordered_order(manager)
    canceled = await manager.put(
        f"{ORDERS}/{order_id}/cancel",
        params={"expected_edit_version": await order_version(manager, order_id)},
    )
    assert canceled.status_code == 200, canceled.text
    assert ACTION not in canceled.json()["actions"]

    refused = await _set(manager, order_id, ["AB-1"])

    assert refused.status_code == 409
    assert refused.json()["code"] == "OrderSupplierOrderNumbersLockedError"


async def test_an_older_edit_version_answers_409(manager) -> None:
    order_id = await _ordered_order(manager)
    version = await order_version(manager, order_id)
    await _set(manager, order_id, ["AB-1"])

    stale = await manager.put(
        f"{ORDERS}/{order_id}/supplier-order-numbers",
        json={"numbers": ["AB-2"], "expected_edit_version": version},
    )

    assert stale.status_code == 409


async def test_an_oversized_list_or_number_answers_422(manager) -> None:
    order_id = await _ordered_order(manager)

    too_many = await _set(manager, order_id, [f"AB-{n}" for n in range(51)])
    too_long = await _set(manager, order_id, ["A" * 101])

    assert too_many.status_code == 422
    assert too_long.status_code == 422


async def test_the_number_filter_matches_a_supplier_number(manager) -> None:
    order_id = await _ordered_order(manager)
    other_id = await _ordered_order(manager)
    await _set(manager, order_id, ["AB-24117", "Lieferung-Müller-7"])

    by_number = (await manager.get(f"{ORDERS}/", params={"order_number": "24117"})).json()
    by_umlaut = (await manager.get(f"{ORDERS}/", params={"order_number": "müller"})).json()
    by_own = (await manager.get(f"{ORDERS}/", params={"order_number": "ORD"})).json()

    assert [o["id"] for o in by_number["items"]] == [order_id]
    assert [o["id"] for o in by_umlaut["items"]] == [order_id]
    assert {o["id"] for o in by_own["items"]} == {order_id, other_id}


async def test_the_order_pickers_search_matches_a_supplier_number(manager) -> None:
    order_id = await _ordered_order(manager)
    await _ordered_order(manager)
    await _set(manager, order_id, ["AB-24117"])

    found = (await manager.get(f"{ORDERS}/", params={"search": "ab-241"})).json()

    assert [o["id"] for o in found["items"]] == [order_id]


async def test_the_global_search_finds_an_order_by_a_supplier_number(manager) -> None:
    order_id = await _ordered_order(manager)
    await _set(manager, order_id, ["AB-24117"])

    body = (await manager.get(SEARCH, params={"q": "AB-24117"})).json()

    group = next(g for g in body["groups"] if g["resource"] == "orders")
    assert group["total"] == 1
    assert group["items"][0]["id"] == order_id
