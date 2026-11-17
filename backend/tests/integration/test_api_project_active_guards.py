"""
Work moved onto or revived on a project that is not active is refused, while
the cleanup of work already on such a project goes through. An order line
moved onto a project on hold and a line closed short reopened on one answer
409 and change nothing. An external assignment takes the lot's project,
whatever project the client names, and is refused while that project is on
hold. Marking a line ordered, delivering, correcting and closing it short
still answer 200 on a project on hold, so forgotten work can be cleaned up.
"""

from datetime import UTC
from datetime import datetime
from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.fulfillment.adapters.outbound.persistence.models.order_item_model import (
    OrderItemOrmModel,
)
from src.modules.platform.const import API_WEB
from src.modules.platform.domain.value_objects.permission import Permission
from src.modules.workspace.adapters.outbound.persistence.models.project_model import ProjectOrmModel
from src.modules.workspace.adapters.outbound.persistence.repositories.project_repository import (
    SqlAlchemyProjectRepository,
)
from src.modules.workspace.domain.entities.project import Project
from tests.integration._edit_versions import line_version
from tests.integration._suppliers import seed_supplier
from tests.integration.test_api_lifecycle_scenarios import Shop
from tests.integration.test_api_production_order_reconciled import _seed_production_settings  # noqa: F401

ORDERS = f"{API_WEB}/orders"
DELIVER = f"{API_WEB}/bought-items-allocations/order-item"


async def _hold(db: AsyncSession, project_id: int) -> None:
    await db.execute(
        update(ProjectOrmModel).where(ProjectOrmModel.id == project_id).values(status="on_hold")
    )
    await db.commit()


async def _project(db: AsyncSession, number: str) -> int:
    project = await SqlAlchemyProjectRepository(db).save(
        Project(id=0, created=datetime.now(UTC), creator_id=1, project_number=number)
    )
    await db.commit()
    return project.id


@pytest.fixture
async def manager(db: AsyncSession, auth_client: Any) -> Any:
    await seed_supplier(db)
    await db.commit()
    return await auth_client(
        permissions=[
            Permission.WRITE_ORDERS,
            Permission.MANAGE_ORDERS,
            Permission.RECEIVE_DELIVERIES,
        ],
        username="guard",
        email="guard@example.com",
    )


async def _line(client: Any, project_id: int) -> tuple[int, int]:
    """An order with a line of 10 for the project, still pending."""
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
    return order_id, int(added.json()["id"])


async def _line_body(client: Any, order_id: int, line_id: int) -> dict[str, Any]:
    order = (await client.get(f"{ORDERS}/{order_id}")).json()
    return dict(next(item for item in order["items"] if item["id"] == line_id))


async def test_moving_a_line_onto_a_project_on_hold_is_refused(
    db: AsyncSession, manager: Any
) -> None:
    home = await _project(db, "P-401")
    held = await _project(db, "P-402")
    active = await _project(db, "P-403")
    await _hold(db, held)
    order_id, line_id = await _line(manager, home)
    url = f"{ORDERS}/{order_id}/items/{line_id}"

    def body(project_id: int, version: int) -> dict[str, Any]:
        return {
            "quantity": 10,
            "unit": "pcs",
            "virtual_name": "Bracket",
            "project_id": project_id,
            "expected_edit_version": version,
        }

    refused = await manager.put(
        url, json=body(held, await line_version(manager, order_id, line_id))
    )
    assert refused.status_code == 409, refused.text
    assert refused.json()["code"] == "ProjectInactiveError"
    assert (await _line_body(manager, order_id, line_id))["project_id"] == home

    moved = await manager.put(
        url, json=body(active, await line_version(manager, order_id, line_id))
    )
    assert moved.status_code == 200, moved.text
    assert (await _line_body(manager, order_id, line_id))["project_id"] == active


async def test_a_line_of_a_project_on_hold_is_cleaned_up_but_not_reopened(
    db: AsyncSession, manager: Any
) -> None:
    project_id = await _project(db, "P-404")
    order_id, line_id = await _line(manager, project_id)
    await _hold(db, project_id)

    marked = await manager.put(f"{ORDERS}/{order_id}/items/{line_id}/mark-ordered")
    delivered = await manager.put(f"{DELIVER}/{line_id}/deliver", params={"quantity": 8})
    (row,) = (await _line_body(manager, order_id, line_id))["delivery_records"]
    corrected = await manager.post(
        f"{ORDERS}/{order_id}/items/{line_id}/deliveries/{row['id']}/correct",
        json={
            "quantity": 1,
            "reason": "Counted twice",
            "expected_edit_version": await line_version(manager, order_id, line_id),
        },
    )
    closed = await manager.post(
        f"{ORDERS}/{order_id}/items/{line_id}/close-short",
        params={"expected_edit_version": await line_version(manager, order_id, line_id)},
    )
    reopened = await manager.post(
        f"{ORDERS}/{order_id}/items/{line_id}/reopen",
        params={"expected_edit_version": await line_version(manager, order_id, line_id)},
    )

    assert [r.status_code for r in (marked, delivered, corrected, closed)] == [200] * 4, [
        r.text for r in (marked, delivered, corrected, closed)
    ]
    assert reopened.status_code == 409, reopened.text
    assert reopened.json()["code"] == "ProjectInactiveError"
    line = await _line_body(manager, order_id, line_id)
    assert (line["quantity"], line["closed_short_at"] is not None) == (7, True)


async def test_an_external_assignment_takes_the_lots_project_and_needs_it_active(
    db: AsyncSession, auth_client: Any
) -> None:
    shop = await Shop.open(db, auth_client, extra_positions=1)
    _first, second = await shop.positions()
    url = f"{API_WEB}/production-lots/{shop.floor.lot_id}/positions/{second}/assign"

    await _hold(db, shop.floor.project_id)
    held = await shop.client.post(url, json={"order_id": shop.order_id, "unit": "pcs"})
    assert held.status_code == 409, held.text
    assert held.json()["code"] == "ProjectInactiveError"

    await db.execute(
        update(ProjectOrmModel)
        .where(ProjectOrmModel.id == shop.floor.project_id)
        .values(status="active")
    )
    await db.commit()
    assigned = await shop.client.post(url, json={"order_id": shop.order_id, "unit": "pcs"})
    assert assigned.status_code == 200, assigned.text
    db.expire_all()
    project_of_line = (
        await db.execute(
            select(OrderItemOrmModel.project_id).where(
                OrderItemOrmModel.lot_position_id == second,
                OrderItemOrmModel.canceled_at.is_(None),
            )
        )
    ).scalar_one()
    assert project_of_line == shop.floor.project_id
