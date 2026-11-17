"""
`fabrication-methods` is one of the 8 reference-table resources a
read-only backend survey found already conforming to the pagination
convention (`FabricationMethodFilterParams` -> `clamp_page` -> a real SQL
`COUNT`), with no prior integration coverage. This is the pagination/sort
vertical,
replicating test_api_customer_crud.py's `TestList` block (its docstring
names it the template) plus one order_by/order_dir assertion per
allow-listed column (`id`, `name`, `created`, `changed`).
"""

from datetime import UTC
from datetime import datetime

import pytest
from sqlalchemy import update

from src.modules.catalogue.adapters.outbound.persistence.models.fabrication_method_model import (
    FabricationMethodOrmModel,
)
from src.modules.platform.const import DEFAULT_PAGE_SIZE
from src.modules.platform.const import MAX_PAGE_SIZE
from src.modules.platform.domain.value_objects.permission import Permission

WRITE = [Permission.WRITE_FABRICATION_METHODS]


@pytest.fixture
async def writer(auth_client):
    return await auth_client(permissions=WRITE)


async def _create(client, name="Milling", **overrides):
    body = {"name": {"enGB": name}} | overrides
    resp = await client.post("/api/v1/web/fabrication-methods/", json=body)
    assert resp.status_code == 201, resp.text
    return resp.json()


class TestList:
    async def test_empty_list_has_a_zero_total(self, writer):
        body = (await writer.get("/api/v1/web/fabrication-methods/")).json()
        assert body["items"] == []
        assert body["total"] == 0

    async def test_limit_caps_the_page_but_not_the_total(self, writer):
        await _create(writer, "Alpha")
        await _create(writer, "Beta")
        await _create(writer, "Gamma")

        body = (await writer.get("/api/v1/web/fabrication-methods/?limit=2")).json()

        assert len(body["items"]) == 2
        assert body["total"] == 3

    async def test_skip_offsets_the_page(self, writer):
        await _create(writer, "Alpha")
        await _create(writer, "Beta")
        await _create(writer, "Gamma")

        first = (await writer.get("/api/v1/web/fabrication-methods/?limit=2")).json()
        second = (await writer.get("/api/v1/web/fabrication-methods/?skip=2&limit=2")).json()

        assert len(second["items"]) == 1
        first_ids = {i["id"] for i in first["items"]}
        assert {i["id"] for i in second["items"]}.isdisjoint(first_ids)

    async def test_an_explicit_limit_above_the_max_is_rejected(self, writer):
        response = await writer.get(f"/api/v1/web/fabrication-methods/?limit={MAX_PAGE_SIZE + 1}")
        assert response.status_code == 422

    async def test_a_bare_request_does_not_return_the_whole_table(self, writer, db):
        """Regression guard, mirroring test_api_customer_crud.py's own
        reasoning: seeded directly via the ORM rather than 100+ live
        requests. `writer` is the only user created so far, so id=1."""
        now = (await writer.get("/api/v1/web/fabrication-methods/")).json()
        assert now["total"] == 0

        row_count = DEFAULT_PAGE_SIZE + 4
        db.add_all(
            FabricationMethodOrmModel(
                name={"enGB": f"Method {i}"},
                creator_id=1,
                created=datetime.now(UTC),
                changed=datetime.now(UTC),
            )
            for i in range(row_count)
        )
        await db.commit()

        body = (await writer.get("/api/v1/web/fabrication-methods/")).json()

        assert body["total"] == row_count
        assert len(body["items"]) == DEFAULT_PAGE_SIZE


class TestSorting:
    async def test_sorts_by_id_both_directions(self, writer):
        await _create(writer, "Alpha")
        await _create(writer, "Beta")

        asc = (
            await writer.get("/api/v1/web/fabrication-methods/?order_by=id&order_dir=asc")
        ).json()
        ids = [i["id"] for i in asc["items"]]
        assert ids == sorted(ids)

        desc = (
            await writer.get("/api/v1/web/fabrication-methods/?order_by=id&order_dir=desc")
        ).json()
        ids = [i["id"] for i in desc["items"]]
        assert ids == sorted(ids, reverse=True)

    async def test_sorts_by_name_both_directions(self, writer):
        await _create(writer, "Zeta")
        await _create(writer, "Alpha")

        asc = (
            await writer.get("/api/v1/web/fabrication-methods/?order_by=name&order_dir=asc")
        ).json()
        names = [i["name"]["enGB"] for i in asc["items"]]
        assert names == sorted(names)

        desc = (
            await writer.get("/api/v1/web/fabrication-methods/?order_by=name&order_dir=desc")
        ).json()
        names = [i["name"]["enGB"] for i in desc["items"]]
        assert names == sorted(names, reverse=True)

    async def test_sorts_by_created_both_directions(self, writer, db):
        ids = [(await _create(writer, f"M{i}"))["id"] for i in range(3)]
        for offset, mid in enumerate(ids):
            await db.execute(
                update(FabricationMethodOrmModel)
                .where(FabricationMethodOrmModel.id == mid)
                .values({"created": datetime(2026, 1, 1 + offset, tzinfo=UTC)})
            )
        await db.commit()

        asc = (
            await writer.get("/api/v1/web/fabrication-methods/?order_by=created&order_dir=asc")
        ).json()
        created = [i["created"] for i in asc["items"]]
        assert created == sorted(created)

        desc = (
            await writer.get("/api/v1/web/fabrication-methods/?order_by=created&order_dir=desc")
        ).json()
        created = [i["created"] for i in desc["items"]]
        assert created == sorted(created, reverse=True)

    async def test_sorts_by_changed_both_directions(self, writer, db):
        ids = [(await _create(writer, f"M{i}"))["id"] for i in range(3)]
        for offset, mid in enumerate(ids):
            await db.execute(
                update(FabricationMethodOrmModel)
                .where(FabricationMethodOrmModel.id == mid)
                .values({"changed": datetime(2026, 2, 1 + offset, tzinfo=UTC)})
            )
        await db.commit()

        asc = (
            await writer.get("/api/v1/web/fabrication-methods/?order_by=changed&order_dir=asc")
        ).json()
        changed = [i["changed"] for i in asc["items"]]
        assert changed == sorted(changed)

        desc = (
            await writer.get("/api/v1/web/fabrication-methods/?order_by=changed&order_dir=desc")
        ).json()
        changed = [i["changed"] for i in desc["items"]]
        assert changed == sorted(changed, reverse=True)
