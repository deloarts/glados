"""
Proves through the API that an order with some lines ordered and others not
yet is partially ordered: a buyer with write:orders alone can still order and
change its pending lines but not its ordered ones, nor cancel the order; a
correction that takes every delivered piece back leaves the order partially
ordered, never draft, and clears the line's delivery date.
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
from tests.integration._edit_versions import order_version
from tests.integration._suppliers import seed_supplier

ORDERS = f"{API_WEB}/orders"
DELIVER = f"{API_WEB}/bought-items-allocations/order-item"


@pytest.fixture(autouse=True)
async def _supplier(db) -> None:
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
async def buyer(manager, auth_client) -> Any:
    return await auth_client(
        permissions=[Permission.WRITE_ORDERS], username="buyer", email="buyer@example.com"
    )


@pytest.fixture
async def project_id(db, manager) -> int:
    project = await SqlAlchemyProjectRepository(db).save(
        Project(id=0, created=datetime.now(UTC), creator_id=1, project_number="P-310")
    )
    await db.commit()
    return project.id


async def _line(client: Any, order_id: int, project_id: int) -> int:
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
    return int(added.json()["id"])


async def _order_with_one_line_ordered(client: Any, project_id: int) -> tuple[int, int, int]:
    created = await client.post(f"{ORDERS}/", json={"supplier_id": 1})
    assert created.status_code == 201, created.text
    order_id = int(created.json()["id"])
    ordered = await _line(client, order_id, project_id)
    pending = await _line(client, order_id, project_id)
    marked = await client.put(f"{ORDERS}/{order_id}/items/{ordered}/mark-ordered")
    assert marked.status_code == 200, marked.text
    return order_id, ordered, pending


async def _reread(client: Any, order_id: int) -> tuple[dict[str, Any], dict[int, dict[str, Any]]]:
    response = await client.get(f"{ORDERS}/{order_id}")
    assert response.status_code == 200, response.text
    order = dict(response.json())
    return order, {int(item["id"]): item for item in order["items"]}


async def test_one_line_ordered_makes_the_order_partially_ordered(buyer, project_id: int) -> None:
    order_id, ordered, pending = await _order_with_one_line_ordered(buyer, project_id)

    order, items = await _reread(buyer, order_id)

    assert order["status"] == "partially_ordered"
    # A new line counts as pending, which a partially ordered order keeps
    # open to the buyer.
    assert set(order["actions"]) == {
        "mark_ordered",
        "deliver",
        "edit_supplier_order_numbers",
        "add_item",
    }
    assert "cancel" not in items[ordered]["actions"]
    assert {"cancel", "mark_ordered", "edit_quantity"} <= set(items[pending]["actions"])


async def test_a_buyer_cannot_cancel_the_ordered_line_but_can_order_the_rest(
    buyer, project_id: int
) -> None:
    order_id, ordered, pending = await _order_with_one_line_ordered(buyer, project_id)

    refused = await buyer.post(
        f"{ORDERS}/{order_id}/items/{ordered}/cancel",
        params={"expected_edit_version": await line_version(buyer, order_id, ordered)},
    )
    canceled_order = await buyer.put(
        f"{ORDERS}/{order_id}/cancel",
        params={"expected_edit_version": await order_version(buyer, order_id)},
    )
    marked = await buyer.put(f"{ORDERS}/{order_id}/items/{pending}/mark-ordered")

    assert refused.status_code == 409, refused.text
    assert refused.json()["code"] == "OrderAlreadySubmittedError"
    assert canceled_order.status_code == 403, canceled_order.text
    assert marked.status_code == 200, marked.text
    order, items = await _reread(buyer, order_id)
    assert items[ordered]["status"] == "ordered"
    assert order["status"] == "ordered"


async def test_a_full_correction_leaves_the_order_partially_ordered(
    manager, project_id: int
) -> None:
    order_id, ordered, _ = await _order_with_one_line_ordered(manager, project_id)
    booked = await manager.put(f"{DELIVER}/{ordered}/deliver", params={"quantity": 4})
    assert booked.status_code == 200, booked.text
    order, items = await _reread(manager, order_id)
    assert order["status"] == "partially_delivered"
    assert items[ordered]["delivery_date"] is not None
    (row,) = items[ordered]["delivery_records"]

    response = await manager.post(
        f"{ORDERS}/{order_id}/items/{ordered}/deliveries/{row['id']}/correct",
        json={
            "quantity": 4,
            "reason": "Booked on the wrong line",
            "expected_edit_version": items[ordered]["edit_version"],
        },
    )

    assert response.status_code == 200, response.text
    order, items = await _reread(manager, order_id)
    assert order["status"] == "partially_ordered"
    assert (items[ordered]["status"], items[ordered]["quantity_delivered"]) == ("ordered", 0)
    assert items[ordered]["delivery_date"] is None
