"""
Settling order lines through HTTP, every outcome read back through a
separate request. Canceling a line that received nothing keeps it on its
order as canceled; a caller without the permission gets 403 and a line named
under another order 404 before the 409 of a line that received pieces.
Closing a line short that received nothing answers 409. A delivery
correction books a negative row that names the corrected row and the reason,
lowers the line's delivered total and reopens the line; it answers 403
without receive:deliveries, 404 for a row of another line, 409 beyond what
the row accepted and 422 for a quantity of nothing or a blank reason.
A line closed short records the close and takes no correction until it is
reopened, which brings its quantity back; a line of a canceled order takes
no correction. Canceling an order closes its partially delivered lines short
and cancels the lines that received nothing.
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


async def _order(client: Any) -> int:
    created = await client.post(f"{ORDERS}/", json={"supplier_id": 1})
    assert created.status_code == 201, created.text
    return int(created.json()["id"])


async def _ordered_line(client: Any, order_id: int, project_id: int, *, delivered: int = 0) -> int:
    """A line of 10 on the order, marked ordered, `delivered` of them
    delivered."""
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
    line_id = int(added.json()["id"])
    marked = await client.put(f"{ORDERS}/{order_id}/items/{line_id}/mark-ordered")
    assert marked.status_code == 200, marked.text
    if delivered:
        booked = await client.put(f"{DELIVER}/{line_id}/deliver", params={"quantity": delivered})
        assert booked.status_code == 200, booked.text
    return line_id


async def _reread(client: Any, order_id: int) -> tuple[dict[str, Any], dict[int, dict[str, Any]]]:
    response = await client.get(f"{ORDERS}/{order_id}")
    assert response.status_code == 200, response.text
    order = dict(response.json())
    return order, {int(item["id"]): item for item in order["items"]}


async def test_canceling_a_line_keeps_it_on_the_order_as_canceled(manager, project_id: int) -> None:
    order_id = await _order(manager)
    canceled_id = await _ordered_line(manager, order_id, project_id)
    kept_id = await _ordered_line(manager, order_id, project_id)

    response = await manager.post(
        f"{ORDERS}/{order_id}/items/{canceled_id}/cancel",
        params={"expected_edit_version": await line_version(manager, order_id, canceled_id)},
    )

    assert response.status_code == 200, response.text
    assert response.json()["status"] == "canceled"
    order, items = await _reread(manager, order_id)
    assert items[canceled_id]["status"] == "canceled"
    assert items[canceled_id]["canceled_at"] is not None
    assert items[kept_id]["status"] == "ordered"
    assert order["status"] == "ordered"


async def test_a_line_with_deliveries_gets_403_and_404_before_the_409(
    manager, auth_client, project_id: int
) -> None:
    order_id = await _order(manager)
    line_id = await _ordered_line(manager, order_id, project_id, delivered=4)
    other_order_id = await _order(manager)
    stranger = await auth_client(permissions=[], username="stranger", email="stranger@example.com")

    version = {"expected_edit_version": await line_version(manager, order_id, line_id)}
    forbidden = await stranger.post(f"{ORDERS}/{order_id}/items/{line_id}/cancel", params=version)
    missing = await manager.post(
        f"{ORDERS}/{other_order_id}/items/{line_id}/cancel", params=version
    )
    refused = await manager.post(f"{ORDERS}/{order_id}/items/{line_id}/cancel", params=version)

    assert (forbidden.status_code, missing.status_code, refused.status_code) == (403, 404, 409)
    assert refused.json()["code"] == "OrderItemCannotBeCanceledError"
    _, items = await _reread(manager, order_id)
    assert items[line_id]["status"] == "partially_delivered"


async def test_closing_short_a_line_that_received_nothing_is_refused(
    manager, project_id: int
) -> None:
    order_id = await _order(manager)
    line_id = await _ordered_line(manager, order_id, project_id)

    response = await manager.post(
        f"{ORDERS}/{order_id}/items/{line_id}/close-short",
        params={"expected_edit_version": await line_version(manager, order_id, line_id)},
    )

    assert response.status_code == 409, response.text
    assert response.json()["code"] == "OrderItemCannotBeClosedShortError"
    _, items = await _reread(manager, order_id)
    assert (items[line_id]["status"], items[line_id]["quantity"]) == ("ordered", 10)


async def test_a_correction_books_a_negative_row_and_reopens_the_line(
    manager, project_id: int
) -> None:
    order_id = await _order(manager)
    line_id = await _ordered_line(manager, order_id, project_id, delivered=10)
    _, items = await _reread(manager, order_id)
    (row,) = items[line_id]["delivery_records"]

    response = await manager.post(
        f"{ORDERS}/{order_id}/items/{line_id}/deliveries/{row['id']}/correct",
        json={
            "quantity": 3,
            "reason": "  Counted twice  ",
            "expected_edit_version": items[line_id]["edit_version"],
        },
    )

    assert response.status_code == 200, response.text
    order, items = await _reread(manager, order_id)
    line = items[line_id]
    assert (line["status"], line["quantity_delivered"]) == ("partially_delivered", 7)
    assert order["status"] == "partially_delivered"
    assert order["delivery_date"] is None
    rows = sorted(line["delivery_records"], key=lambda r: r["id"])
    assert [(r["quantity"], r["corrects_delivery_id"], r["correction_reason"]) for r in rows] == [
        (10, None, None),
        (-3, row["id"], "Counted twice"),
    ]
    assert [r["id"] for r in response.json()["delivery_records"]] == [r["id"] for r in rows]


async def test_a_correction_is_refused_with_its_status_codes(
    manager, auth_client, project_id: int
) -> None:
    order_id = await _order(manager)
    line_id = await _ordered_line(manager, order_id, project_id, delivered=4)
    other_id = await _ordered_line(manager, order_id, project_id, delivered=2)
    _, items = await _reread(manager, order_id)
    (row,) = items[line_id]["delivery_records"]
    (other_row,) = items[other_id]["delivery_records"]
    buyer = await auth_client(
        permissions=[Permission.WRITE_ORDERS, Permission.MANAGE_ORDERS],
        username="buyer",
        email="buyer@example.com",
    )
    correct = f"{ORDERS}/{order_id}/items/{line_id}/deliveries"
    version = items[line_id]["edit_version"]

    forbidden = await buyer.post(
        f"{correct}/{row['id']}/correct",
        json={"quantity": 1, "reason": "x", "expected_edit_version": version},
    )
    missing = await manager.post(
        f"{correct}/{other_row['id']}/correct",
        json={"quantity": 1, "reason": "x", "expected_edit_version": version},
    )
    too_many = await manager.post(
        f"{correct}/{row['id']}/correct",
        json={"quantity": 5, "reason": "x", "expected_edit_version": version},
    )
    nothing = await manager.post(
        f"{correct}/{row['id']}/correct",
        json={"quantity": 0, "reason": "x", "expected_edit_version": version},
    )
    blank = await manager.post(
        f"{correct}/{row['id']}/correct",
        json={"quantity": 1, "reason": " ", "expected_edit_version": version},
    )

    assert [r.status_code for r in (forbidden, missing, too_many, nothing, blank)] == [
        403,
        404,
        409,
        422,
        422,
    ]
    assert missing.json()["code"] == "OrderItemDeliveryNotFoundError"
    assert too_many.json()["code"] == "DeliveryCannotBeCorrectedError"
    _, items = await _reread(manager, order_id)
    assert items[line_id]["quantity_delivered"] == 4
    assert len(items[line_id]["delivery_records"]) == 1


async def test_canceling_an_order_closes_partially_delivered_lines_short(
    manager, project_id: int
) -> None:
    order_id = await _order(manager)
    partial_id = await _ordered_line(manager, order_id, project_id, delivered=6)
    open_id = await _ordered_line(manager, order_id, project_id)

    response = await manager.put(
        f"{ORDERS}/{order_id}/cancel",
        params={"expected_edit_version": await order_version(manager, order_id)},
    )

    assert response.status_code == 200, response.text
    order, items = await _reread(manager, order_id)
    assert order["status"] == "canceled"
    assert (items[partial_id]["status"], items[partial_id]["quantity"]) == ("delivered", 6)
    assert items[partial_id]["canceled_at"] is None
    assert items[open_id]["status"] == "canceled"


async def test_a_line_closed_short_is_reopened_before_a_correction(
    manager, project_id: int
) -> None:
    order_id = await _order(manager)
    line_id = await _ordered_line(manager, order_id, project_id, delivered=8)
    closed = await manager.post(
        f"{ORDERS}/{order_id}/items/{line_id}/close-short",
        params={"expected_edit_version": await line_version(manager, order_id, line_id)},
    )
    assert closed.status_code == 200, closed.text
    assert (closed.json()["closed_short_from"], closed.json()["quantity"]) == (10, 8)
    assert closed.json()["closed_short_at"] is not None
    assert "reopen" in closed.json()["actions"]
    _, items = await _reread(manager, order_id)
    (row,) = items[line_id]["delivery_records"]
    correct = f"{ORDERS}/{order_id}/items/{line_id}/deliveries/{row['id']}/correct"

    refused = await manager.post(
        correct,
        json={
            "quantity": 1,
            "reason": "Counted twice",
            "expected_edit_version": items[line_id]["edit_version"],
        },
    )
    reopen = f"{ORDERS}/{order_id}/items/{line_id}/reopen"
    reopened = await manager.post(
        reopen, params={"expected_edit_version": await line_version(manager, order_id, line_id)}
    )
    again = await manager.post(
        reopen, params={"expected_edit_version": await line_version(manager, order_id, line_id)}
    )
    corrected = await manager.post(
        correct,
        json={
            "quantity": 1,
            "reason": "Counted twice",
            "expected_edit_version": await line_version(manager, order_id, line_id),
        },
    )

    assert refused.status_code == 409, refused.text
    assert "reopen it" in refused.json()["detail"]
    assert reopened.status_code == 200, reopened.text
    assert (reopened.json()["quantity"], reopened.json()["status"]) == (10, "partially_delivered")
    assert reopened.json()["closed_short_at"] is None
    assert again.status_code == 409
    assert again.json()["code"] == "OrderItemCannotBeReopenedError"
    assert corrected.status_code == 200, corrected.text
    _, items = await _reread(manager, order_id)
    assert (items[line_id]["quantity"], items[line_id]["quantity_delivered"]) == (10, 7)


async def test_a_line_of_a_canceled_order_takes_no_correction(manager, project_id: int) -> None:
    order_id = await _order(manager)
    line_id = await _ordered_line(manager, order_id, project_id, delivered=10)
    other_id = await _ordered_line(manager, order_id, project_id)
    canceled = await manager.put(
        f"{ORDERS}/{order_id}/cancel",
        params={"expected_edit_version": await order_version(manager, order_id)},
    )
    assert canceled.status_code == 200, canceled.text
    _, items = await _reread(manager, order_id)
    (row,) = items[line_id]["delivery_records"]

    refused = await manager.post(
        f"{ORDERS}/{order_id}/items/{line_id}/deliveries/{row['id']}/correct",
        json={
            "quantity": 1,
            "reason": "Counted twice",
            "expected_edit_version": items[line_id]["edit_version"],
        },
    )

    assert refused.status_code == 409, refused.text
    assert "is canceled" in refused.json()["detail"]
    assert items[other_id]["status"] == "canceled"


async def test_submit_and_cancel_answer_the_order_with_its_lines(manager, project_id: int) -> None:
    order_id = await _order(manager)
    added = await manager.post(
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

    submitted = await manager.put(f"{ORDERS}/{order_id}/submit")
    assert submitted.status_code == 200, submitted.text
    assert [item["status"] for item in submitted.json()["items"]] == ["ordered"]

    canceled = await manager.put(
        f"{ORDERS}/{order_id}/cancel",
        params={"expected_edit_version": await order_version(manager, order_id)},
    )
    assert canceled.status_code == 200, canceled.text
    assert canceled.json()["status"] == "canceled"
    assert [item["status"] for item in canceled.json()["items"]] == ["canceled"]
