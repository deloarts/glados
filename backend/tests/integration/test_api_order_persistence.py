"""
Proves that the order status routes persist what they report. Creating an
order, requesting and submitting it, and marking its lines requested,
ordered or ready for pickup, one at a time and in bulk, are each read back
through a separate request, so a use case that forgets to commit its unit
of work fails here instead of silently losing the write.
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
from tests.integration._suppliers import seed_supplier

ORDERS = f"{API_WEB}/orders"


@pytest.fixture(autouse=True)
async def _supplier(db) -> None:
    """Supplier #1, which the orders and lines here name."""
    await seed_supplier(db)


@pytest.fixture
async def manager(db, auth_client) -> Any:
    await db.commit()
    return await auth_client(permissions=[Permission.WRITE_ORDERS, Permission.MANAGE_ORDERS])


@pytest.fixture
async def project_id(db, manager) -> int:
    project = await SqlAlchemyProjectRepository(db).save(
        Project(id=0, created=datetime.now(UTC), creator_id=1, project_number="P-200")
    )
    await db.commit()
    return project.id


async def _create_order(client: Any) -> int:
    response = await client.post(f"{ORDERS}/", json={"supplier_id": 1})
    assert response.status_code == 201, response.text
    return int(response.json()["id"])


async def _add_item(client: Any, order_id: int, project_id: int, name: str) -> int:
    response = await client.post(
        f"{ORDERS}/{order_id}/items",
        json={
            "order_id": order_id,
            "supplier_id": 1,
            "project_id": project_id,
            "virtual_name": name,
            "quantity": 2,
            "unit": "pcs",
        },
    )
    assert response.status_code == 201, response.text
    return int(response.json()["id"])


async def _reread(client: Any, order_id: int) -> dict[str, Any]:
    response = await client.get(f"{ORDERS}/{order_id}")
    assert response.status_code == 200, response.text
    return dict(response.json())


def _item(order: dict[str, Any], item_id: int) -> dict[str, Any]:
    return next(i for i in order["items"] if i["id"] == item_id)


async def test_order_create_request_and_submit_are_persisted(manager) -> None:
    requested_id = await _create_order(manager)
    assert (await _reread(manager, requested_id))["status"] == "draft"

    requested = await manager.put(f"{ORDERS}/{requested_id}/request")
    assert requested.status_code == 200, requested.text
    assert (await _reread(manager, requested_id))["status"] == "requested"

    submitted_id = await _create_order(manager)
    submitted = await manager.put(f"{ORDERS}/{submitted_id}/submit")
    assert submitted.status_code == 200, submitted.text
    reread = await _reread(manager, submitted_id)
    assert reread["status"] == "ordered"
    assert reread["ordered_date"] is not None


async def test_single_item_marks_are_persisted(manager, project_id: int) -> None:
    order_id = await _create_order(manager)
    item_id = await _add_item(manager, order_id, project_id, "Freight")

    marked = await manager.put(f"{ORDERS}/{order_id}/items/{item_id}/mark-requested")
    assert marked.status_code == 200, marked.text
    order = await _reread(manager, order_id)
    assert _item(order, item_id)["status"] == "requested"
    assert order["status"] == "requested"

    marked = await manager.put(f"{ORDERS}/{order_id}/items/{item_id}/mark-ordered")
    assert marked.status_code == 200, marked.text
    order = await _reread(manager, order_id)
    assert _item(order, item_id)["status"] == "ordered"
    assert order["status"] == "ordered"

    marked = await manager.put(f"{ORDERS}/{order_id}/items/{item_id}/mark-ready-for-pickup")
    assert marked.status_code == 200, marked.text
    order = await _reread(manager, order_id)
    assert _item(order, item_id)["ready_for_pickup_date"] is not None


async def test_bulk_item_marks_are_persisted(manager, project_id: int) -> None:
    order_id = await _create_order(manager)
    item_ids = [
        await _add_item(manager, order_id, project_id, "Freight"),
        await _add_item(manager, order_id, project_id, "Packaging"),
    ]

    marked = await manager.put(f"{ORDERS}/{order_id}/mark-items-requested")
    assert marked.status_code == 200, marked.text
    order = await _reread(manager, order_id)
    assert [_item(order, i)["status"] for i in item_ids] == ["requested", "requested"]
    assert order["status"] == "requested"

    marked = await manager.put(f"{ORDERS}/{order_id}/mark-items-ordered")
    assert marked.status_code == 200, marked.text
    order = await _reread(manager, order_id)
    assert [_item(order, i)["status"] for i in item_ids] == ["ordered", "ordered"]
    assert order["status"] == "ordered"


async def test_a_mark_records_the_changing_user(manager, auth_client, project_id: int) -> None:
    order_id = await _create_order(manager)
    item_id = await _add_item(manager, order_id, project_id, "Freight")
    before = await _reread(manager, order_id)
    editor = await auth_client(
        permissions=[Permission.WRITE_ORDERS, Permission.MANAGE_ORDERS],
        username="editor",
        email="editor@example.com",
    )

    marked = await editor.put(f"{ORDERS}/{order_id}/items/{item_id}/mark-requested")

    assert marked.status_code == 200, marked.text
    order = await _reread(manager, order_id)
    item = _item(order, item_id)
    for row in (order, item):
        assert row["creator_id"] == before["creator_id"]
        assert row["changed_by_id"] not in (None, before["creator_id"])
        assert row["changed_by"]["id"] == row["changed_by_id"]
    assert order["changed_by_id"] == item["changed_by_id"]
