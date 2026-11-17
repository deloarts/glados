"""
Deliveries under the global tolerances over HTTP, on a virtual line, which
has no catalogue item and takes the order settings' values: a delivery
within the over-delivery tolerance is booked beyond the quantity, one beyond
it answers 422, and the booking within the under-delivery tolerance closes
the line short.
"""

from datetime import UTC
from datetime import datetime
from typing import Any

import pytest

from src.modules.catalogue.adapters.outbound.persistence.models.admin_settings_model.orders import (
    AdminOrderSettingsOrmModel,
)
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
    settings = await db.get(AdminOrderSettingsOrmModel, 1)
    settings.over_delivery_tolerance_percent = 10.0
    settings.under_delivery_tolerance_percent = 10.0
    await db.commit()
    return await auth_client(
        permissions=[
            Permission.WRITE_ORDERS,
            Permission.MANAGE_ORDERS,
            Permission.RECEIVE_DELIVERIES,
        ]
    )


@pytest.fixture
async def line(db, client) -> tuple[int, int]:
    """An ordered virtual line of 10 pieces, as (order id, line id)."""
    project = await SqlAlchemyProjectRepository(db).save(
        Project(id=0, created=datetime.now(UTC), creator_id=1, project_number="P-310")
    )
    await db.commit()
    order = await client.post(f"{ORDERS}/", json={"supplier_id": 1})
    assert order.status_code == 201, order.text
    order_id = int(order.json()["id"])
    added = await client.post(
        f"{ORDERS}/{order_id}/items",
        json={
            "order_id": order_id,
            "supplier_id": 1,
            "project_id": project.id,
            "virtual_name": "Bracket",
            "quantity": 10,
            "unit": "pcs",
        },
    )
    assert added.status_code == 201, added.text
    line_id = int(added.json()["id"])
    marked = await client.put(f"{ORDERS}/{order_id}/items/{line_id}/mark-ordered")
    assert marked.status_code == 200, marked.text
    return order_id, line_id


async def _item(client: Any, order_id: int, line_id: int) -> dict[str, Any]:
    order = (await client.get(f"{ORDERS}/{order_id}")).json()
    return next(item for item in order["items"] if item["id"] == line_id)


async def test_a_delivery_within_the_over_tolerance_goes_beyond_the_quantity(client, line) -> None:
    order_id, line_id = line

    booked = await client.put(f"{DELIVER}/{line_id}/deliver", params={"quantity": 11})

    assert booked.status_code == 200, booked.text
    item = await _item(client, order_id, line_id)
    assert (item["status"], item["quantity"], item["quantity_delivered"]) == ("delivered", 10, 11)


async def test_a_delivery_beyond_the_over_tolerance_is_refused(client, line) -> None:
    order_id, line_id = line

    refused = await client.put(f"{DELIVER}/{line_id}/deliver", params={"quantity": 12})

    assert refused.status_code == 422, refused.text
    assert "over-delivery tolerance allows 1.000 more" in refused.json()["detail"]
    assert (await _item(client, order_id, line_id))["quantity_delivered"] == 0


async def test_the_booking_within_the_under_tolerance_closes_the_line_short(client, line) -> None:
    order_id, line_id = line

    booked = await client.put(f"{DELIVER}/{line_id}/deliver", params={"quantity": 9})

    assert booked.status_code == 200, booked.text
    item = await _item(client, order_id, line_id)
    assert (item["status"], item["quantity"], item["closed_short_from"]) == ("delivered", 9, 10)
    assert item["closed_short_at"] is not None
