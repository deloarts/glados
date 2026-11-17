"""
Edit versions over HTTP: an edit or an irreversible action sent with the
edit version the client read goes through and moves it, one sent with an
older version answers 409 and changes nothing, one sent without it is
refused with 422 before anything is read, and a delivery, which only moves
derived fields, leaves it alone. A reopen checks the version as the close
it undoes does.
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
DELIVER = f"{API_WEB}/bought-items-allocations/order-item"


@pytest.fixture(autouse=True)
async def _supplier(db) -> None:
    """Supplier #1, which the orders and lines here name."""
    await seed_supplier(db)


@pytest.fixture
async def client(db, auth_client) -> Any:
    client = await auth_client(
        permissions=[
            Permission.WRITE_ORDERS,
            Permission.MANAGE_ORDERS,
            Permission.RECEIVE_DELIVERIES,
        ]
    )
    project = await SqlAlchemyProjectRepository(db).save(
        Project(id=0, created=datetime.now(UTC), creator_id=1, project_number="P-330")
    )
    await db.commit()
    client.project_id = project.id
    return client


async def _line(client: Any) -> tuple[int, dict[str, Any]]:
    order = await client.post(f"{ORDERS}/", json={"supplier_id": 1})
    order_id = int(order.json()["id"])
    added = await client.post(
        f"{ORDERS}/{order_id}/items",
        json={
            "order_id": order_id,
            "supplier_id": 1,
            "project_id": client.project_id,
            "virtual_name": "Bracket",
            "quantity": 10,
            "unit": "pcs",
        },
    )
    assert added.status_code == 201, added.text
    return order_id, added.json()


def _edit(line: dict[str, Any], **changes: Any) -> dict[str, Any]:
    return {"quantity": line["quantity"], "unit": line["unit"], **changes}


async def test_an_edit_with_the_version_read_goes_through_and_moves_it(client) -> None:
    order_id, line = await _line(client)
    assert line["edit_version"] == 0

    edited = await client.put(
        f"{ORDERS}/{order_id}/items/{line['id']}",
        json=_edit(line, quantity=12, expected_edit_version=0),
    )

    assert edited.status_code == 200, edited.text
    assert edited.json()["edit_version"] == 1


async def test_an_edit_with_an_older_version_is_refused(client) -> None:
    order_id, line = await _line(client)
    first = await client.put(
        f"{ORDERS}/{order_id}/items/{line['id']}",
        json=_edit(line, note="first", expected_edit_version=0),
    )
    assert first.status_code == 200, first.text

    stale = await client.put(
        f"{ORDERS}/{order_id}/items/{line['id']}",
        json=_edit(line, quantity=4, expected_edit_version=0),
    )

    assert stale.status_code == 409, stale.text
    assert stale.json()["code"] == "ConcurrentModificationError"
    items = (await client.get(f"{ORDERS}/{order_id}")).json()["items"]
    assert items[0]["quantity"] == 10


async def test_a_cancel_with_an_older_version_is_refused(client) -> None:
    order_id, _line_body = await _line(client)
    changed = await client.put(
        f"{ORDERS}/{order_id}", json={"note": "changed", "expected_edit_version": 0}
    )
    assert changed.status_code == 200, changed.text

    stale = await client.put(f"{ORDERS}/{order_id}/cancel", params={"expected_edit_version": 0})
    current = await client.put(f"{ORDERS}/{order_id}/cancel", params={"expected_edit_version": 1})

    assert stale.status_code == 409, stale.text
    assert current.status_code == 200, current.text
    assert current.json()["status"] == "canceled"
    # The cancel moved the order and the line it canceled.
    assert current.json()["edit_version"] == 2
    assert current.json()["items"][0]["edit_version"] == 1


async def test_an_edit_or_a_cancel_without_a_version_is_refused(client) -> None:
    order_id, line = await _line(client)

    edit = await client.put(f"{ORDERS}/{order_id}/items/{line['id']}", json=_edit(line, note="x"))
    cancel = await client.put(f"{ORDERS}/{order_id}/cancel")

    assert (edit.status_code, cancel.status_code) == (422, 422)
    order = (await client.get(f"{ORDERS}/{order_id}")).json()
    assert order["status"] != "canceled"
    assert order["items"][0]["note"] != "x"


async def test_a_delivery_leaves_the_edit_version_alone(client) -> None:
    order_id, line = await _line(client)
    marked = await client.put(f"{ORDERS}/{order_id}/items/{line['id']}/mark-ordered")
    assert marked.status_code == 200, marked.text

    delivered = await client.put(f"{DELIVER}/{line['id']}/deliver", params={"quantity": 4})

    assert delivered.status_code == 200, delivered.text
    assert delivered.json()["status"] == "partially_delivered"
    assert delivered.json()["edit_version"] == 0


async def test_a_reopen_needs_the_version_read_of_the_line(client) -> None:
    order_id, line = await _line(client)
    line_url = f"{ORDERS}/{order_id}/items/{line['id']}"
    assert (await client.put(f"{line_url}/mark-ordered")).status_code == 200
    assert (await client.put(f"{DELIVER}/{line['id']}/deliver", params={"quantity": 4})).is_success
    closed = await client.post(f"{line_url}/close-short", params={"expected_edit_version": 0})
    assert closed.status_code == 200, closed.text

    without = await client.post(f"{line_url}/reopen")
    stale = await client.post(f"{line_url}/reopen", params={"expected_edit_version": 0})
    reopened = await client.post(
        f"{line_url}/reopen", params={"expected_edit_version": closed.json()["edit_version"]}
    )

    assert without.status_code == 422, without.text
    assert stale.status_code == 409, stale.text
    assert stale.json()["code"] == "ConcurrentModificationError"
    assert reopened.status_code == 200, reopened.text
    assert reopened.json()["edit_version"] == closed.json()["edit_version"] + 1
