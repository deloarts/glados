"""
The order item PUT through HTTP: a new quantity on a partially delivered
line answers 409 and changes nothing, and closing the line short instead
closes the line and its order. Every outcome is read back through a separate
request.
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
from tests.integration._edit_versions import line_version
from tests.integration._suppliers import seed_supplier

ORDERS = f"{API_WEB}/orders"
DELIVER = f"{API_WEB}/bought-items-allocations/order-item"


@pytest.fixture(autouse=True)
async def _supplier(db) -> None:
    """Supplier #1, which the orders and lines here name."""
    await seed_supplier(db)


@pytest.fixture
async def manager(db, auth_client) -> Any:
    await db.commit()
    return await auth_client(
        permissions=[
            Permission.WRITE_ORDERS,
            Permission.MANAGE_ORDERS,
            Permission.RECEIVE_DELIVERIES,
        ]
    )


@pytest.fixture
async def project_id(db, manager) -> int:
    project = await SqlAlchemyProjectRepository(db).save(
        Project(id=0, created=datetime.now(UTC), creator_id=1, project_number="P-300")
    )
    await db.commit()
    return project.id


async def _partially_delivered_line(client: Any, project_id: int) -> tuple[int, int]:
    """An order with one line of 10, marked ordered, 6 of them delivered."""
    created = await client.post(f"{ORDERS}/", json={"supplier_id": 1})
    assert created.status_code == 201, created.text
    order_id = int(created.json()["id"])

    added = await client.post(
        f"{ORDERS}/{order_id}/items",
        json={
            "order_id": order_id,
            "supplier_id": 1,
            "project_id": project_id,
            "virtual_name": "Bracket",
            "quantity": 10,
            "unit": "pcs",
        },
    )
    assert added.status_code == 201, added.text
    item_id = int(added.json()["id"])

    marked = await client.put(f"{ORDERS}/{order_id}/items/{item_id}/mark-ordered")
    assert marked.status_code == 200, marked.text
    delivered = await client.put(f"{DELIVER}/{item_id}/deliver", params={"quantity": 6})
    assert delivered.status_code == 200, delivered.text
    return order_id, item_id


async def _reread(
    client: Any, order_id: int, item_id: int
) -> tuple[dict[str, Any], dict[str, Any]]:
    response = await client.get(f"{ORDERS}/{order_id}")
    assert response.status_code == 200, response.text
    order = dict(response.json())
    item = next(i for i in order["items"] if i["id"] == item_id)
    return order, item


async def test_a_partially_delivered_line_takes_no_new_quantity(manager, project_id: int) -> None:
    order_id, item_id = await _partially_delivered_line(manager, project_id)

    response = await manager.put(
        f"{ORDERS}/{order_id}/items/{item_id}",
        json={
            "quantity": 4,
            "unit": "pcs",
            "expected_edit_version": await line_version(manager, order_id, item_id),
        },
    )

    assert response.status_code == 409, response.text
    assert response.json()["code"] == "OrderItemQuantityNotEditableError"
    order, item = await _reread(manager, order_id, item_id)
    assert item["quantity"] == 10
    assert item["status"] == "partially_delivered"
    assert order["status"] == "partially_delivered"


async def test_closing_the_line_short_closes_line_and_order(manager, project_id: int) -> None:
    order_id, item_id = await _partially_delivered_line(manager, project_id)

    response = await manager.post(
        f"{ORDERS}/{order_id}/items/{item_id}/close-short",
        params={"expected_edit_version": await line_version(manager, order_id, item_id)},
    )

    assert response.status_code == 200, response.text
    assert response.json()["status"] == "delivered"
    order, item = await _reread(manager, order_id, item_id)
    assert item["quantity"] == 6
    assert item["status"] == "delivered"
    assert order["status"] == "delivered"
    assert order["delivery_date"] is not None


async def test_a_line_that_received_goods_keeps_its_unit(manager, project_id: int) -> None:
    order_id, item_id = await _partially_delivered_line(manager, project_id)

    response = await manager.put(
        f"{ORDERS}/{order_id}/items/{item_id}",
        json={
            "quantity": 10,
            "unit": "M",
            "expected_edit_version": await line_version(manager, order_id, item_id),
        },
    )

    assert response.status_code == 409, response.text
    assert response.json()["code"] == "OrderItemReceivedLockedError"
    _, item = await _reread(manager, order_id, item_id)
    assert item["unit"] == "pcs"


async def test_a_line_that_received_goods_still_takes_a_new_price(manager, project_id: int) -> None:
    order_id, item_id = await _partially_delivered_line(manager, project_id)

    response = await manager.put(
        f"{ORDERS}/{order_id}/items/{item_id}",
        json={
            "quantity": 10,
            "unit": "pcs",
            "price": 1250,
            "note": "Invoice price",
            "expected_edit_version": await line_version(manager, order_id, item_id),
        },
    )

    assert response.status_code == 200, response.text
    _, item = await _reread(manager, order_id, item_id)
    assert (item["price"], item["note"]) == (1250, "Invoice price")
