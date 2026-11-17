"""
Updating an order through HTTP. A supplier change carries to the lines that
named the old supplier while none is ordered, and is refused with 409 once
one is. The bulk expected delivery date reaches only the lines that still
wait for goods, and only when the request sends a date.
"""

from typing import Any

import pytest

from src.modules.catalogue.adapters.outbound.persistence.repositories.supplier_repository import (
    SqlAlchemySupplierRepository,
)
from src.modules.catalogue.domain.entities.supplier import Supplier
from src.modules.catalogue.domain.value_objects.supplier_level import SupplierLevel
from tests.integration._edit_versions import order_version
from tests.integration._suppliers import seed_supplier
from tests.integration.repository_reads._graph import make
from tests.integration.test_api_order_line_settlement import ORDERS
from tests.integration.test_api_order_line_settlement import _order
from tests.integration.test_api_order_line_settlement import _ordered_line
from tests.integration.test_api_order_line_settlement import _reread
from tests.integration.test_api_order_line_settlement import manager  # noqa: F401
from tests.integration.test_api_order_line_settlement import project_id  # noqa: F401


@pytest.fixture(autouse=True)
async def _supplier(db) -> None:
    """Supplier #1, which the orders and lines here name."""
    await seed_supplier(db)


@pytest.fixture
async def other_supplier(db: Any) -> int:
    """A second supplier besides #1, which the orders here are placed with."""
    repo = SqlAlchemySupplierRepository(db)
    ids = []
    for name, code in (("Acme", "ACM"), ("Other", "OTH")):
        saved = await repo.save(
            make(
                Supplier,
                name=name,
                vat_id=f"AT{code}",
                edp_code=code,
                level=SupplierLevel.A,
                creator_id=1,
            )
        )
        ids.append(saved.id)
    await db.commit()
    return max(ids)


async def _pending_line(client: Any, order_id: int, project: int) -> int:
    added = await client.post(
        f"{ORDERS}/{order_id}/items",
        json={
            "order_id": order_id,
            "supplier_id": 1,
            "project_id": project,
            "virtual_name": "Bracket",
            "quantity": 10,
            "unit": "pcs",
        },
    )
    assert added.status_code == 201, added.text
    return int(added.json()["id"])


async def test_a_supplier_change_carries_to_the_open_lines(
    manager: Any,  # noqa: F811
    project_id: int,  # noqa: F811
    other_supplier: int,
) -> None:
    order_id = await _order(manager)
    line_id = await _pending_line(manager, order_id, project_id)

    response = await manager.put(
        f"{ORDERS}/{order_id}",
        json={
            "supplier_id": other_supplier,
            "expected_edit_version": await order_version(manager, order_id),
        },
    )

    assert response.status_code == 200, response.text
    order, items = await _reread(manager, order_id)
    assert order["supplier_id"] == other_supplier
    assert items[line_id]["supplier_id"] == other_supplier


async def test_a_supplier_change_is_refused_once_a_line_is_ordered(
    manager: Any,  # noqa: F811
    project_id: int,  # noqa: F811
    other_supplier: int,
) -> None:
    order_id = await _order(manager)
    await _ordered_line(manager, order_id, project_id)

    response = await manager.put(
        f"{ORDERS}/{order_id}",
        json={
            "supplier_id": other_supplier,
            "expected_edit_version": await order_version(manager, order_id),
        },
    )

    assert response.status_code == 409, response.text
    assert response.json()["code"] == "OrderSupplierLockedError"


async def test_the_bulk_date_reaches_only_lines_that_wait_for_goods(
    manager: Any,  # noqa: F811
    project_id: int,  # noqa: F811
) -> None:
    order_id = await _order(manager)
    open_id = await _ordered_line(manager, order_id, project_id)
    delivered_id = await _ordered_line(manager, order_id, project_id, delivered=10)
    _, before = await _reread(manager, order_id)

    without_date = await manager.put(
        f"{ORDERS}/{order_id}",
        json={
            "note": "x",
            "update_items_delivery_date": True,
            "expected_edit_version": await order_version(manager, order_id),
        },
    )
    with_date = await manager.put(
        f"{ORDERS}/{order_id}",
        json={
            "expected_delivery_date": "2026-12-01",
            "update_items_delivery_date": True,
            "expected_edit_version": await order_version(manager, order_id),
        },
    )

    assert without_date.status_code == 200, without_date.text
    assert with_date.status_code == 200, with_date.text
    _, items = await _reread(manager, order_id)
    assert items[open_id]["expected_delivery_date"] == "2026-12-01"
    assert (
        items[delivered_id]["expected_delivery_date"]
        == before[delivered_id]["expected_delivery_date"]
    )
