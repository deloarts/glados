"""
`suppliers` is one of the 8 reference-table resources already conforming
to the pagination convention (`SupplierFilterParams` -> `clamp_page` -> a
real SQL `COUNT`), but with no integration coverage proving it. This is
the pagination/sort vertical, replicating test_api_customer_crud.py's
`TestList` block (its docstring names it the template) plus one
order_by/order_dir assertion per allow-listed column (`id`, `name`,
`created`, `changed`).
"""

from datetime import UTC
from datetime import datetime

import pytest
from sqlalchemy import update

from src.modules.catalogue.adapters.outbound.persistence.models.supplier_model import (
    SupplierOrmModel,
)
from src.modules.platform.const import DEFAULT_PAGE_SIZE
from src.modules.platform.const import MAX_PAGE_SIZE
from src.modules.platform.domain.value_objects.permission import Permission

WRITE = [Permission.WRITE_SUPPLIERS]


@pytest.fixture
async def writer(auth_client):
    return await auth_client(permissions=WRITE)


async def _create(client, name="Acme Fasteners", **overrides):
    body = {"name": name, "level": "B"} | overrides
    resp = await client.post("/api/v1/web/suppliers/", json=body)
    assert resp.status_code == 201, resp.text
    return resp.json()


class TestList:
    async def test_empty_list_has_a_zero_total(self, writer):
        body = (await writer.get("/api/v1/web/suppliers/")).json()
        assert body["items"] == []
        assert body["total"] == 0

    async def test_limit_caps_the_page_but_not_the_total(self, writer):
        await _create(writer, "Alpha")
        await _create(writer, "Beta")
        await _create(writer, "Gamma")

        body = (await writer.get("/api/v1/web/suppliers/?limit=2")).json()

        assert len(body["items"]) == 2
        assert body["total"] == 3

    async def test_skip_offsets_the_page(self, writer):
        await _create(writer, "Alpha")
        await _create(writer, "Beta")
        await _create(writer, "Gamma")

        first = (await writer.get("/api/v1/web/suppliers/?limit=2")).json()
        second = (await writer.get("/api/v1/web/suppliers/?skip=2&limit=2")).json()

        assert len(second["items"]) == 1
        first_ids = {i["id"] for i in first["items"]}
        assert {i["id"] for i in second["items"]}.isdisjoint(first_ids)

    async def test_an_explicit_limit_above_the_max_is_rejected(self, writer):
        response = await writer.get(f"/api/v1/web/suppliers/?limit={MAX_PAGE_SIZE + 1}")
        assert response.status_code == 422

    async def test_a_bare_request_does_not_return_the_whole_table(self, writer, db):
        """Regression guard: a list request with no `limit` must never
        mean "everything". Seeded directly via the ORM rather than 100+ live
        requests, mirroring test_api_customer_crud.py's own reasoning.
        `writer` is the only user created so far, so id=1."""
        now = (await writer.get("/api/v1/web/suppliers/")).json()
        assert now["total"] == 0

        row_count = DEFAULT_PAGE_SIZE + 4
        db.add_all(
            SupplierOrmModel(
                name=f"Supplier {i}",
                level="A",
                creator_id=1,
                created=datetime.now(UTC),
                changed=datetime.now(UTC),
            )
            for i in range(row_count)
        )
        await db.commit()

        body = (await writer.get("/api/v1/web/suppliers/")).json()

        assert body["total"] == row_count
        assert len(body["items"]) == DEFAULT_PAGE_SIZE


class TestSorting:
    async def test_sorts_by_id_both_directions(self, writer):
        await _create(writer, "Alpha")
        await _create(writer, "Beta")

        asc = (await writer.get("/api/v1/web/suppliers/?order_by=id&order_dir=asc")).json()
        ids = [i["id"] for i in asc["items"]]
        assert ids == sorted(ids)

        desc = (await writer.get("/api/v1/web/suppliers/?order_by=id&order_dir=desc")).json()
        ids = [i["id"] for i in desc["items"]]
        assert ids == sorted(ids, reverse=True)

    async def test_sorts_by_name_both_directions(self, writer):
        await _create(writer, "Zeta")
        await _create(writer, "Alpha")

        asc = (await writer.get("/api/v1/web/suppliers/?order_by=name&order_dir=asc")).json()
        names = [i["name"] for i in asc["items"]]
        assert names == sorted(names)

        desc = (await writer.get("/api/v1/web/suppliers/?order_by=name&order_dir=desc")).json()
        names = [i["name"] for i in desc["items"]]
        assert names == sorted(names, reverse=True)

    async def test_sorts_by_created_both_directions(self, writer, db):
        ids = [(await _create(writer, f"S{i}"))["id"] for i in range(3)]
        for offset, sid in enumerate(ids):
            await db.execute(
                update(SupplierOrmModel)
                .where(SupplierOrmModel.id == sid)
                .values({"created": datetime(2026, 1, 1 + offset, tzinfo=UTC)})
            )
        await db.commit()

        asc = (await writer.get("/api/v1/web/suppliers/?order_by=created&order_dir=asc")).json()
        created = [i["created"] for i in asc["items"]]
        assert created == sorted(created)

        desc = (await writer.get("/api/v1/web/suppliers/?order_by=created&order_dir=desc")).json()
        created = [i["created"] for i in desc["items"]]
        assert created == sorted(created, reverse=True)

    async def test_sorts_by_changed_both_directions(self, writer, db):
        ids = [(await _create(writer, f"S{i}"))["id"] for i in range(3)]
        for offset, sid in enumerate(ids):
            await db.execute(
                update(SupplierOrmModel)
                .where(SupplierOrmModel.id == sid)
                .values({"changed": datetime(2026, 2, 1 + offset, tzinfo=UTC)})
            )
        await db.commit()

        asc = (await writer.get("/api/v1/web/suppliers/?order_by=changed&order_dir=asc")).json()
        changed = [i["changed"] for i in asc["items"]]
        assert changed == sorted(changed)

        desc = (await writer.get("/api/v1/web/suppliers/?order_by=changed&order_dir=desc")).json()
        changed = [i["changed"] for i in desc["items"]]
        assert changed == sorted(changed, reverse=True)


async def _ids(client, query):
    resp = await client.get(f"/api/v1/web/suppliers/?{query}")
    assert resp.status_code == 200, resp.text
    return {i["id"] for i in resp.json()["items"]}


class TestColumnFilters:
    """Each management-table row filter, one match and one miss."""

    async def test_filters_by_legal_name_substring(self, writer):
        hit = await _create(writer, "Alpha", legal_name="Alpha Holding Ltd")
        await _create(writer, "Beta", legal_name="Beta plc")

        assert await _ids(writer, "legal_name=holding") == {hit["id"]}
        assert await _ids(writer, "legal_name=nomatch") == set()

    async def test_filters_by_level(self, writer):
        hit = await _create(writer, "Alpha", level="A")
        await _create(writer, "Beta", level="C")

        assert await _ids(writer, "level=A") == {hit["id"]}
        assert await _ids(writer, "level=B") == set()

    async def test_filters_by_address_across_street_postal_code_and_city(self, writer):
        by_street = await _create(writer, "Alpha", street="Highfield Road 1")
        by_postal = await _create(writer, "Beta", postal_code="4020")
        by_city = await _create(writer, "Gamma", city="Leeds")
        await _create(writer, "Delta", street="Ring Road 2", postal_code="1010", city="London")

        assert await _ids(writer, "address=highfield") == {by_street["id"]}
        assert await _ids(writer, "address=402") == {by_postal["id"]}
        assert await _ids(writer, "address=leeds") == {by_city["id"]}
        assert await _ids(writer, "address=york") == set()

    async def test_filters_by_country_substring(self, writer):
        hit = await _create(writer, "Alpha", country="AT")
        await _create(writer, "Beta", country="DE")

        assert await _ids(writer, "country=at") == {hit["id"]}
        assert await _ids(writer, "country=CH") == set()

    async def test_filters_by_email_substring(self, writer):
        hit = await _create(writer, "Alpha", email="sales@alpha.example")
        await _create(writer, "Beta", email="info@beta.example")

        assert await _ids(writer, "email=alpha") == {hit["id"]}
        assert await _ids(writer, "email=gamma") == set()

    async def test_filters_by_capability(self, auth_client):
        client = await auth_client(permissions=[*WRITE, Permission.WRITE_FABRICATION_METHODS])
        milling = (
            await client.post(
                "/api/v1/web/fabrication-methods/", json={"name": {"enGB": "Milling"}}
            )
        ).json()
        turning = (
            await client.post(
                "/api/v1/web/fabrication-methods/", json={"name": {"enGB": "Turning"}}
            )
        ).json()
        hit = await _create(client, "Alpha", capability_ids=[milling["id"]])
        await _create(client, "Beta")

        assert await _ids(client, f"capability_id={milling['id']}") == {hit["id"]}
        assert await _ids(client, f"capability_id={turning['id']}") == set()

    async def test_filters_by_article_group(self, auth_client):
        client = await auth_client(permissions=[*WRITE, Permission.WRITE_ARTICLE_GROUPS])
        screws = (
            await client.post("/api/v1/web/article-groups/", json={"name": {"enGB": "Screws"}})
        ).json()
        nuts = (
            await client.post("/api/v1/web/article-groups/", json={"name": {"enGB": "Nuts"}})
        ).json()
        hit = await _create(client, "Alpha", article_group_ids=[screws["id"]])
        await _create(client, "Beta")

        assert await _ids(client, f"article_group_id={screws['id']}") == {hit["id"]}
        assert await _ids(client, f"article_group_id={nuts['id']}") == set()

    async def test_filters_by_creator(self, writer):
        hit = await _create(writer, "Alpha")

        assert await _ids(writer, f"creator_id={hit['creator_id']}") == {hit["id"]}
        assert await _ids(writer, f"creator_id={hit['creator_id'] + 999}") == set()

    async def test_created_bounds_include_the_whole_named_day(self, writer, db):
        hit = await _create(writer, "Alpha")
        other = await _create(writer, "Beta")
        await db.execute(
            update(SupplierOrmModel)
            .where(SupplierOrmModel.id == hit["id"])
            .values({"created": datetime(2026, 3, 10, 12, 0, tzinfo=UTC)})
        )
        await db.execute(
            update(SupplierOrmModel)
            .where(SupplierOrmModel.id == other["id"])
            .values({"created": datetime(2026, 3, 20, 12, 0, tzinfo=UTC)})
        )
        await db.commit()

        assert await _ids(writer, "created_from=2026-03-10&created_to=2026-03-10") == {hit["id"]}
        assert await _ids(writer, "created_from=2026-03-11&created_to=2026-03-19") == set()

    async def test_changed_bounds_include_the_whole_named_day(self, writer, db):
        hit = await _create(writer, "Alpha")
        other = await _create(writer, "Beta")
        await db.execute(
            update(SupplierOrmModel)
            .where(SupplierOrmModel.id == hit["id"])
            .values({"changed": datetime(2026, 4, 10, 12, 0, tzinfo=UTC)})
        )
        await db.execute(
            update(SupplierOrmModel)
            .where(SupplierOrmModel.id == other["id"])
            .values({"changed": datetime(2026, 4, 20, 12, 0, tzinfo=UTC)})
        )
        await db.commit()

        assert await _ids(writer, "changed_from=2026-04-10&changed_to=2026-04-10") == {hit["id"]}
        assert await _ids(writer, "changed_from=2026-04-11&changed_to=2026-04-19") == set()
