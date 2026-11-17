"""
A new order line names a supplier and a project that must exist, and the
project must be active: an unknown supplier, an unknown project and a
deleted one, which reads as gone, answer 404, a completed or archived project
409, a project on hold 409 naming order lines, and nothing is added in any case.
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
from src.modules.workspace.domain.value_objects.project_status import ProjectStatus
from tests.integration._suppliers import seed_supplier

ORDERS = f"{API_WEB}/orders"


@pytest.fixture
async def manager(db, auth_client) -> Any:
    await seed_supplier(db)
    return await auth_client(permissions=[Permission.WRITE_ORDERS, Permission.MANAGE_ORDERS])


async def _project(db, number: str, **values: Any) -> int:
    project = await SqlAlchemyProjectRepository(db).save(
        Project(id=0, created=datetime.now(UTC), creator_id=1, project_number=number, **values)
    )
    await db.commit()
    return project.id


async def _add_line(client: Any, order_id: int, *, project_id: int, supplier_id: int = 1):
    return await client.post(
        f"{ORDERS}/{order_id}/items",
        json={
            "order_id": order_id,
            "supplier_id": supplier_id,
            "project_id": project_id,
            "virtual_name": "Bracket",
            "quantity": 1,
            "unit": "pcs",
        },
    )


async def _lines(client: Any, order_id: int) -> list[Any]:
    items: list[Any] = (await client.get(f"{ORDERS}/{order_id}")).json()["items"]
    return items


async def test_order_item_references_a_missing_project_or_supplier_answer_404(db, manager) -> None:
    order_id = int((await manager.post(f"{ORDERS}/", json={"supplier_id": 1})).json()["id"])
    project_id = await _project(db, "P-REF-1")

    no_project = await _add_line(manager, order_id, project_id=999_999)
    no_supplier = await _add_line(manager, order_id, project_id=project_id, supplier_id=999_999)

    assert no_project.status_code == 404, no_project.text
    assert no_project.json()["code"] == "ProjectNotFoundError"
    assert no_supplier.status_code == 404, no_supplier.text
    assert no_supplier.json()["code"] == "SupplierNotFoundError"
    assert await _lines(manager, order_id) == []


@pytest.mark.parametrize(
    ("values", "status", "code"),
    [
        ({"deleted": True}, 404, "ProjectNotFoundError"),
        ({"status": ProjectStatus.COMPLETED}, 409, "ProjectInactiveError"),
        ({"status": ProjectStatus.ARCHIVED}, 409, "ProjectInactiveError"),
    ],
)
async def test_order_item_references_a_deleted_or_inactive_project_are_refused(
    db, manager, values: dict[str, Any], status: int, code: str
) -> None:
    order_id = int((await manager.post(f"{ORDERS}/", json={"supplier_id": 1})).json()["id"])
    project_id = await _project(db, "P-REF-2", **values)

    refused = await _add_line(manager, order_id, project_id=project_id)

    assert refused.status_code == status, refused.text
    assert refused.json()["code"] == code
    assert await _lines(manager, order_id) == []


async def test_a_project_on_hold_refuses_a_new_order_line_naming_order_lines(db, manager) -> None:
    order_id = int((await manager.post(f"{ORDERS}/", json={"supplier_id": 1})).json()["id"])
    project_id = await _project(db, "P-REF-3", status=ProjectStatus.ON_HOLD)

    refused = await _add_line(manager, order_id, project_id=project_id)

    assert refused.status_code == 409, refused.text
    body = refused.json()
    assert body["code"] == "ProjectInactiveError"
    assert "only an active project takes new order lines" in body["detail"]
    assert await _lines(manager, order_id) == []
