"""
Proves that creating and updating a project persist what they report and
publish their events. Each write is read back through a separate request,
so a use case that forgets to commit its unit of work fails here instead of
silently losing the write.
"""

from typing import Any

from src.modules.platform.const import API_WEB
from src.modules.platform.domain.value_objects.permission import Permission
from src.modules.workspace.domain.events.project_events import ProjectCreated
from src.modules.workspace.domain.events.project_events import ProjectUpdated
from tests.integration._edit_versions import row_version

PROJECTS = f"{API_WEB}/projects"


async def _reread(client: Any, project_id: int) -> dict[str, Any]:
    response = await client.get(f"{PROJECTS}/{project_id}")
    assert response.status_code == 200, response.text
    return dict(response.json())


async def test_create_and_update_are_persisted(auth_client, published_events) -> None:
    client = await auth_client(permissions=[Permission.WRITE_PROJECTS, Permission.MANAGE_PROJECTS])

    created = await client.post(f"{PROJECTS}/", json={"project_number": "P-PERSIST"})
    assert created.status_code == 201, created.text
    project_id = created.json()["id"]
    assert (await _reread(client, project_id))["project_number"] == "P-PERSIST"

    updated = await client.put(
        f"{PROJECTS}/{project_id}",
        json={
            "expected_edit_version": await row_version(client, f"{PROJECTS}/{project_id}"),
            "project_number": "P-PERSIST",
            "description": "Persisted",
            "production_time_budget": 120,
            "required_delivery_date_made": "2026-12-01",
            "propagate_delivery_date_made": True,
        },
    )
    assert updated.status_code == 200, updated.text

    project = await _reread(client, project_id)
    assert project["description"] == "Persisted"
    assert project["production_time_budget"] == 120
    assert project["required_delivery_date_made"] == "2026-12-01"
    assert [type(e) for e in published_events] == [ProjectCreated, ProjectUpdated]
