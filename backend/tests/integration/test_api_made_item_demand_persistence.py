"""
Proves that the made item demand write routes persist what they report.
Each step, from creating a demand through editing, bucketing, changing its
status and setting or removing a stock allocation to deleting it, is read
back through a separate request, so a use case that forgets to commit its
unit of work fails here instead of silently losing the write.
"""

from datetime import UTC
from datetime import datetime
from typing import Any

import pytest

from src.modules.catalogue.adapters.outbound.persistence.repositories.made_item_repository.item import (
    SqlAlchemyMadeItemRepository,
)
from src.modules.catalogue.domain.entities.made_item import MadeItem
from src.modules.catalogue.domain.value_objects.data_source import DataSource
from src.modules.catalogue.domain.value_objects.made_item_status import MadeItemCatalogueStatus
from src.modules.platform.const import API_WEB
from src.modules.platform.domain.value_objects.permission import Permission
from src.modules.workspace.adapters.outbound.persistence.repositories.project_repository import (
    SqlAlchemyProjectRepository,
)
from src.modules.workspace.domain.entities.project import Project

DEMANDS = f"{API_WEB}/made-items-demands"
ALLOCATIONS = f"{API_WEB}/made-items-allocations"
BUCKETS = f"{API_WEB}/made-items-demand-buckets"


@pytest.fixture
async def planner(auth_client) -> Any:
    return await auth_client(
        permissions=[
            Permission.WRITE_DEMAND_ITEMS,
            Permission.MANAGE_DEMAND_ITEMS,
            Permission.WRITE_ALLOCATIONS,
        ]
    )


@pytest.fixture
async def demand_body(db, planner) -> dict[str, Any]:
    """Seeds the project and made item a demand points at and returns the
    body that creates one."""
    project = await SqlAlchemyProjectRepository(db).save(
        Project(id=0, created=datetime.now(UTC), creator_id=1, project_number="P-100")
    )
    item = await SqlAlchemyMadeItemRepository(db).save(
        MadeItem(
            id=0,
            created=datetime.now(UTC),
            changed=datetime.now(UTC),
            changes=[],
            archived=False,
            revision="0",
            revision_date=None,
            revision_note=None,
            article_name="Bracket",
            status=MadeItemCatalogueStatus.ACTIVE,
            data_source=DataSource.WEB,
            part_number="M-100",
            material=None,
            mass=None,
            base_size=None,
            note=None,
            weblink=None,
            files=[],
            creator_id=1,
            approver_id=None,
            bought_item_id=None,
            source_item_id=None,
            article_group_ids=[],
            successor_item_id=None,
            changed_by_id=None,
        )
    )
    await db.commit()
    return {"made_item_id": item.id, "project_id": project.id, "quantity": 5, "unit": "pcs"}


async def _create(client: Any, body: dict[str, Any]) -> int:
    response = await client.post(f"{DEMANDS}/", json=body)
    assert response.status_code == 201, response.text
    return int(response.json()["id"])


async def _reread(client: Any, demand_id: int) -> dict[str, Any]:
    response = await client.get(f"{DEMANDS}/{demand_id}")
    assert response.status_code == 200, response.text
    return dict(response.json())


async def test_demand_writes_are_persisted(planner, demand_body: dict[str, Any]) -> None:
    demand_id = await _create(planner, demand_body)
    assert (await _reread(planner, demand_id))["quantity"] == 5

    updated = await planner.put(f"{DEMANDS}/{demand_id}", json={"quantity": 7, "unit": "pcs"})
    assert updated.status_code == 200, updated.text
    assert (await _reread(planner, demand_id))["quantity"] == 7

    bucket = await planner.post(f"{BUCKETS}/", json={"name": "Urgent", "color": "#ff0000"})
    assert bucket.status_code == 201, bucket.text
    bucketed = await planner.put(
        f"{DEMANDS}/{demand_id}/bucket", json={"bucket_id": bucket.json()["id"]}
    )
    assert bucketed.status_code == 200, bucketed.text
    assert (await _reread(planner, demand_id))["bucket_id"] == bucket.json()["id"]

    # Only the two intents are set by hand; the other statuses follow from
    # the allocations. A fulfilled demand is not deleted, so a second demand
    # takes the status write.
    fulfilled_id = await _create(planner, demand_body)
    moved = await planner.put(
        f"{DEMANDS}/{fulfilled_id}/status", params={"new_status": "fulfilled"}
    )
    assert moved.status_code == 200, moved.text
    assert (await _reread(planner, fulfilled_id))["status"] == "fulfilled"

    deleted = await planner.delete(f"{DEMANDS}/{demand_id}")
    assert deleted.status_code == 200, deleted.text
    assert (await planner.get(f"{DEMANDS}/{demand_id}")).status_code == 404


async def test_stock_allocation_writes_are_persisted(planner, demand_body: dict[str, Any]) -> None:
    demand_id = await _create(planner, demand_body)

    async def stock_quantities() -> list[float]:
        response = await planner.get(f"{ALLOCATIONS}/demand/{demand_id}")
        assert response.status_code == 200, response.text
        return [a["quantity"] for a in response.json() if a["source"] == "stock"]

    allocated = await planner.put(f"{ALLOCATIONS}/demand/{demand_id}/stock", json={"quantity": 2})
    assert allocated.status_code == 200, allocated.text
    assert await stock_quantities() == [2]
    assert (await _reread(planner, demand_id))["status"] == "allocated"

    removed = await planner.delete(f"{ALLOCATIONS}/demand/{demand_id}/stock")
    assert removed.status_code == 204, removed.text
    assert await stock_quantities() == []
    assert (await _reread(planner, demand_id))["status"] == "open"
