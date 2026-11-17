"""
`products` is one of the 8 reference-table resources conforming to the
pagination convention (`ProductFilterParams` -> `clamp_page` -> a real SQL
`COUNT`). `test_api_product_project.py` covers CRUD and cross-aggregate FK
validation but not pagination/sorting. This is that missing vertical,
replicating test_api_customer_crud.py's `TestList` block (its docstring
names it the template) plus one order_by/order_dir assertion per
allow-listed column (`id`, `product_number`, `created`).
"""

from datetime import UTC
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import update

from src.modules.platform.const import DEFAULT_PAGE_SIZE
from src.modules.platform.const import MAX_PAGE_SIZE
from src.modules.platform.domain.value_objects.permission import Permission
from src.modules.workspace.adapters.outbound.persistence.models.product_model import ProductOrmModel

WRITE = [Permission.WRITE_PROJECTS]

# The seeded default timezone, whose days the date filters read; stored
# timestamps stay UTC.
_TENANT_ZONE = ZoneInfo("Europe/Vienna")


@pytest.fixture
async def writer(auth_client):
    return await auth_client(permissions=WRITE)


async def _create(client, number="P-001", **overrides):
    body = {"product_number": number} | overrides
    resp = await client.post("/api/v1/web/products/", json=body)
    assert resp.status_code == 201, resp.text
    return resp.json()


class TestList:
    async def test_empty_list_has_a_zero_total(self, writer):
        body = (await writer.get("/api/v1/web/products/")).json()
        assert body["items"] == []
        assert body["total"] == 0

    async def test_limit_caps_the_page_but_not_the_total(self, writer):
        await _create(writer, "P-001")
        await _create(writer, "P-002")
        await _create(writer, "P-003")

        body = (await writer.get("/api/v1/web/products/?limit=2")).json()

        assert len(body["items"]) == 2
        assert body["total"] == 3

    async def test_skip_offsets_the_page(self, writer):
        await _create(writer, "P-001")
        await _create(writer, "P-002")
        await _create(writer, "P-003")

        first = (await writer.get("/api/v1/web/products/?limit=2")).json()
        second = (await writer.get("/api/v1/web/products/?skip=2&limit=2")).json()

        assert len(second["items"]) == 1
        first_ids = {i["id"] for i in first["items"]}
        assert {i["id"] for i in second["items"]}.isdisjoint(first_ids)

    async def test_an_explicit_limit_above_the_max_is_rejected(self, writer):
        response = await writer.get(f"/api/v1/web/products/?limit={MAX_PAGE_SIZE + 1}")
        assert response.status_code == 422

    async def test_a_bare_request_does_not_return_the_whole_table(self, writer, db):
        """Regression guard, mirroring test_api_customer_crud.py's own
        reasoning: seeded directly via the ORM rather than 100+ live
        requests. `writer` is the only user created so far, so id=1."""
        now = (await writer.get("/api/v1/web/products/")).json()
        assert now["total"] == 0

        row_count = DEFAULT_PAGE_SIZE + 4
        created = datetime.now(UTC)
        db.add_all(
            ProductOrmModel(
                product_number=f"P-BULK-{i}",
                designated_user_id=1,
                creator_id=1,
                created=created,
            )
            for i in range(row_count)
        )
        await db.commit()

        body = (await writer.get("/api/v1/web/products/")).json()

        assert body["total"] == row_count
        assert len(body["items"]) == DEFAULT_PAGE_SIZE


class TestSorting:
    async def test_sorts_by_id_both_directions(self, writer):
        await _create(writer, "P-001")
        await _create(writer, "P-002")

        asc = (await writer.get("/api/v1/web/products/?order_by=id&order_dir=asc")).json()
        ids = [i["id"] for i in asc["items"]]
        assert ids == sorted(ids)

        desc = (await writer.get("/api/v1/web/products/?order_by=id&order_dir=desc")).json()
        ids = [i["id"] for i in desc["items"]]
        assert ids == sorted(ids, reverse=True)

    async def test_sorts_by_product_number_both_directions(self, writer):
        await _create(writer, "P-ZETA")
        await _create(writer, "P-ALPHA")

        asc = (
            await writer.get("/api/v1/web/products/?order_by=product_number&order_dir=asc")
        ).json()
        numbers = [i["product_number"] for i in asc["items"]]
        assert numbers == sorted(numbers)

        desc = (
            await writer.get("/api/v1/web/products/?order_by=product_number&order_dir=desc")
        ).json()
        numbers = [i["product_number"] for i in desc["items"]]
        assert numbers == sorted(numbers, reverse=True)

    async def test_sorts_by_created_both_directions(self, writer, db):
        ids = [(await _create(writer, f"P-{i:03d}"))["id"] for i in range(3)]
        for offset, pid in enumerate(ids):
            await db.execute(
                update(ProductOrmModel)
                .where(ProductOrmModel.id == pid)
                .values({"created": datetime(2026, 1, 1 + offset, tzinfo=UTC)})
            )
        await db.commit()

        asc = (await writer.get("/api/v1/web/products/?order_by=created&order_dir=asc")).json()
        created = [i["created"] for i in asc["items"]]
        assert created == sorted(created)

        desc = (await writer.get("/api/v1/web/products/?order_by=created&order_dir=desc")).json()
        created = [i["created"] for i in desc["items"]]
        assert created == sorted(created, reverse=True)


async def _ids(client, query):
    resp = await client.get(f"/api/v1/web/products/?{query}")
    assert resp.status_code == 200, resp.text
    return {i["id"] for i in resp.json()["items"]}


class TestColumnFilters:
    """Each newly added management-table row filter, one match and one miss."""

    async def test_filters_by_creator(self, writer):
        hit = await _create(writer, "P-001")

        assert await _ids(writer, f"creator_id={hit['creator_id']}") == {hit["id"]}
        assert await _ids(writer, f"creator_id={hit['creator_id'] + 999}") == set()

    async def test_created_bounds_include_the_whole_named_day(self, writer, db):
        hit = await _create(writer, "P-001")
        other = await _create(writer, "P-002")
        await db.execute(
            update(ProductOrmModel)
            .where(ProductOrmModel.id == hit["id"])
            .values({"created": datetime(2026, 3, 10, 23, 30, tzinfo=_TENANT_ZONE).astimezone(UTC)})
        )
        await db.execute(
            update(ProductOrmModel)
            .where(ProductOrmModel.id == other["id"])
            .values({"created": datetime(2026, 3, 20, 0, 0, tzinfo=UTC)})
        )
        await db.commit()

        assert await _ids(writer, "created_from=2026-03-10&created_to=2026-03-10") == {hit["id"]}
        assert await _ids(writer, "created_from=2026-03-11&created_to=2026-03-19") == set()
