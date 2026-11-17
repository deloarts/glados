"""
The `/projects` endpoint gains an `ids` filter, precedent
`DemandItemFilterParams.ids` in bought_item_schema.py, for
batch-resolving project references collected from other aggregates (a
catalogue item's demands/order lines carry only `project_id`, never the
full project). Mirrors test_api_projects_pagination.py's client/fixture
style (the docstring there names `test_api_customer_crud.py`'s `TestList`
block as its own template; this file is the same shape one level down).

`ProjectFilterParams.ids` also needed the endpoint's binding switched from
`Depends()` to `Annotated[ProjectFilterParams, Query()]` (see the note on
`DemandItemFilterParams` for why a `list[...]` field silently arrives as
None otherwise). A live request through the real ASGI app, as done here,
is what actually proves that wiring works, not just unit-level DTO/repo
coverage.
"""

import pytest

from src.modules.platform.domain.value_objects.permission import Permission

WRITE = [Permission.WRITE_PROJECTS]


@pytest.fixture
async def writer(auth_client):
    return await auth_client(permissions=WRITE)


async def _create(client, number="J-001", **overrides):
    body = {"project_number": number} | overrides
    resp = await client.post("/api/v1/web/projects/", json=body)
    assert resp.status_code == 201, resp.text
    return resp.json()


class TestIdsFilter:
    async def test_ids_returns_exactly_the_requested_projects(self, writer):
        p1 = await _create(writer, "J-001")
        p2 = await _create(writer, "J-002")
        await _create(writer, "J-003")

        body = (await writer.get(f"/api/v1/web/projects/?ids={p1['id']}&ids={p2['id']}")).json()

        assert body["total"] == 2
        assert {i["id"] for i in body["items"]} == {p1["id"], p2["id"]}

    async def test_omitted_ids_returns_all(self, writer):
        await _create(writer, "J-001")
        await _create(writer, "J-002")
        await _create(writer, "J-003")

        body = (await writer.get("/api/v1/web/projects/")).json()

        assert body["total"] == 3
        assert len(body["items"]) == 3
