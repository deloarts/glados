"""
Proves through the API that marking a line ordered stores the line's own
ordered date, read back through a separate request, and that the
single-line mark routes refuse a line whose status they do not accept with a
409 and the stable code OrderItemCannotBeMarkedError, leaving the line as it
was. A refused line still gets 403 for a caller without the permission and
404 under another order before that 409, for the marks and for removing a
delivered line.
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


@pytest.fixture(autouse=True)
async def _supplier(db) -> None:
    """Supplier #1, which the orders and lines here name."""
    await seed_supplier(db)


@pytest.fixture
async def manager(db, auth_client) -> Any:
    await db.commit()
    # manage:orders lets a mark reach an order past REQUESTED, so a refusal
    # can only come from the line's own status.
    return await auth_client(permissions=[Permission.WRITE_ORDERS, Permission.MANAGE_ORDERS])


@pytest.fixture
async def project_id(db, manager) -> int:
    project = await SqlAlchemyProjectRepository(db).save(
        Project(id=0, created=datetime.now(UTC), creator_id=1, project_number="P-300")
    )
    await db.commit()
    return project.id


async def _order_with_line(client: Any, project_id: int) -> tuple[int, int]:
    order = await client.post(f"{ORDERS}/", json={"supplier_id": 1})
    assert order.status_code == 201, order.text
    order_id = int(order.json()["id"])
    line = await client.post(
        f"{ORDERS}/{order_id}/items",
        json={
            "order_id": order_id,
            "supplier_id": 1,
            "project_id": project_id,
            "virtual_name": "Freight",
            "quantity": 2,
            "unit": "pcs",
        },
    )
    assert line.status_code == 201, line.text
    return order_id, int(line.json()["id"])


async def _reread_line(client: Any, order_id: int, line_id: int) -> dict[str, Any]:
    response = await client.get(f"{ORDERS}/{order_id}")
    assert response.status_code == 200, response.text
    return dict(next(i for i in response.json()["items"] if i["id"] == line_id))


async def test_mark_ordered_stores_the_line_ordered_date(manager, project_id: int) -> None:
    order_id, line_id = await _order_with_line(manager, project_id)
    assert (await _reread_line(manager, order_id, line_id))["ordered_date"] is None

    marked = await manager.put(f"{ORDERS}/{order_id}/items/{line_id}/mark-ordered")
    assert marked.status_code == 200, marked.text

    line = await _reread_line(manager, order_id, line_id)
    assert line["status"] == "ordered"
    assert line["ordered_date"] is not None


@pytest.mark.parametrize("route", ["mark-ordered", "mark-requested"])
async def test_marking_an_ordered_line_again_is_refused_with_409(
    manager, project_id: int, route: str
) -> None:
    order_id, line_id = await _order_with_line(manager, project_id)
    marked = await manager.put(f"{ORDERS}/{order_id}/items/{line_id}/mark-ordered")
    assert marked.status_code == 200, marked.text
    ordered_date = (await _reread_line(manager, order_id, line_id))["ordered_date"]

    refused = await manager.put(f"{ORDERS}/{order_id}/items/{line_id}/{route}")

    assert refused.status_code == 409, refused.text
    assert refused.json()["code"] == "OrderItemCannotBeMarkedError"
    line = await _reread_line(manager, order_id, line_id)
    assert (line["status"], line["ordered_date"]) == ("ordered", ordered_date)


async def _other_order(client: Any) -> int:
    other = await client.post(f"{ORDERS}/", json={"supplier_id": 1})
    assert other.status_code == 201, other.text
    return int(other.json()["id"])


@pytest.mark.parametrize("route", ["mark-ordered", "mark-requested"])
async def test_a_refused_line_still_gets_403_and_404_before_the_409(
    manager, auth_client, project_id: int, route: str
) -> None:
    order_id, line_id = await _order_with_line(manager, project_id)
    marked = await manager.put(f"{ORDERS}/{order_id}/items/{line_id}/mark-ordered")
    assert marked.status_code == 200, marked.text
    other_order_id = await _other_order(manager)
    stranger = await auth_client(permissions=[], username="stranger", email="stranger@example.com")

    forbidden = await stranger.put(f"{ORDERS}/{order_id}/items/{line_id}/{route}")
    missing = await manager.put(f"{ORDERS}/{other_order_id}/items/{line_id}/{route}")
    refused = await manager.put(f"{ORDERS}/{order_id}/items/{line_id}/{route}")

    assert (forbidden.status_code, missing.status_code, refused.status_code) == (403, 404, 409)
    assert (await _reread_line(manager, order_id, line_id))["status"] == "ordered"


async def test_removing_a_delivered_line_still_gets_403_and_404_before_the_409(
    manager, auth_client, project_id: int
) -> None:
    order_id, line_id = await _order_with_line(manager, project_id)
    marked = await manager.put(f"{ORDERS}/{order_id}/items/{line_id}/mark-ordered")
    assert marked.status_code == 200, marked.text
    receiver = await auth_client(
        permissions=[Permission.RECEIVE_DELIVERIES], username="receiver", email="rx@example.com"
    )
    delivered = await receiver.put(
        f"{API_WEB}/bought-items-allocations/order-item/{line_id}/deliver"
    )
    assert delivered.status_code == 200, delivered.text
    other_order_id = await _other_order(manager)
    stranger = await auth_client(permissions=[], username="stranger", email="stranger@example.com")

    version = {"expected_edit_version": await line_version(manager, order_id, line_id)}
    forbidden = await stranger.delete(f"{ORDERS}/{order_id}/items/{line_id}", params=version)
    missing = await manager.delete(f"{ORDERS}/{other_order_id}/items/{line_id}", params=version)
    refused = await manager.delete(f"{ORDERS}/{order_id}/items/{line_id}", params=version)

    assert (forbidden.status_code, missing.status_code, refused.status_code) == (403, 404, 409)
    assert refused.json()["code"] == "OrderItemCannotBeRemovedError"
    assert (await _reread_line(manager, order_id, line_id))["status"] == "delivered"
