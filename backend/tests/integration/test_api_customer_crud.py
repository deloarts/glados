"""
A full create -> read -> list -> update -> delete round trip over HTTP,
through the real SqlAlchemyCustomerRepository and a real database.

Chosen as the representative vertical because it is the simplest CRUD
aggregate in the codebase (no allocations, no lot/scheduling coupling),
so what it actually exercises is the *plumbing* every other vertical
shares: request-schema validation, entity <-> DTO <-> response-schema
mapping, repository persistence and filtering, and pagination envelopes.
Unit tests cover each of those pieces in isolation with fakes; this file
checks that they compose.
"""

from datetime import UTC
from datetime import datetime

import pytest
from sqlalchemy import text
from sqlalchemy import update

from src.modules.catalogue.adapters.outbound.persistence.models.customer_model import (
    CustomerOrmModel,
)
from src.modules.platform.const import DEFAULT_PAGE_SIZE
from src.modules.platform.const import MAX_PAGE_SIZE
from src.modules.platform.domain.value_objects.permission import Permission
from tests.integration._edit_versions import row_version

WRITE = [Permission.WRITE_PROJECTS]
MANAGE = [Permission.WRITE_PROJECTS, Permission.MANAGE_PROJECTS]

FULL_PAYLOAD = {
    "name": "ACME Manufacturing",
    "legal_name": "ACME Manufacturing Ltd",
    "vat_id": "ATU12345678",
    "level": "A",
    "street": "Highfield Road 1",
    "city": "Vienna",
    "country": "AT",
    "postal_code": "1010",
    "email": "office@acme.example",
    "phone": "+44 20 7946 0123",
    "weblink": "https://acme.example",
}


@pytest.fixture
async def writer(auth_client):
    return await auth_client(permissions=WRITE)


@pytest.fixture
async def manager(auth_client):
    return await auth_client(permissions=MANAGE)


# ── Create ────────────────────────────────────────────────────────────


class TestCreate:
    @pytest.mark.smoke
    async def test_returns_201_with_the_persisted_entity(self, writer):
        response = await writer.post("/api/v1/web/customers/", json=FULL_PAYLOAD)

        assert response.status_code == 201
        body = response.json()
        assert body["id"] > 0
        assert body["name"] == "ACME Manufacturing"
        assert body["level"] == "A"

    async def test_every_supplied_field_round_trips(self, writer):
        body = (await writer.post("/api/v1/web/customers/", json=FULL_PAYLOAD)).json()

        for field, expected in FULL_PAYLOAD.items():
            assert body[field] == expected, f"{field} did not round trip"

    async def test_level_defaults_to_b_when_omitted(self, writer):
        body = (await writer.post("/api/v1/web/customers/", json={"name": "Minimal"})).json()
        assert body["level"] == "B"

    async def test_optional_fields_default_to_null(self, writer):
        body = (await writer.post("/api/v1/web/customers/", json={"name": "Minimal"})).json()
        assert body["vat_id"] is None
        assert body["city"] is None

    async def test_records_the_creating_user(self, writer):
        body = (await writer.post("/api/v1/web/customers/", json=FULL_PAYLOAD)).json()
        assert body["creator_id"] > 0


# ── Request validation (422 before any domain code runs) ──────────────


class TestRequestValidation:
    async def test_missing_required_name_is_422(self, writer):
        assert (await writer.post("/api/v1/web/customers/", json={"level": "A"})).status_code == 422

    async def test_empty_name_is_422(self, writer):
        response = await writer.post("/api/v1/web/customers/", json={"name": ""})
        assert response.status_code == 422

    async def test_level_outside_abc_is_422(self, writer):
        response = await writer.post("/api/v1/web/customers/", json={"name": "X", "level": "Z"})
        assert response.status_code == 422

    async def test_country_must_be_two_characters(self, writer):
        response = await writer.post("/api/v1/web/customers/", json={"name": "X", "country": "AUT"})
        assert response.status_code == 422

    async def test_validation_runs_before_authorization(self, auth_client):
        """A malformed body from an unauthorized user is still a 422,
        worth pinning because the opposite order would leak whether a
        given payload would have been valid."""
        client = await auth_client(permissions=[])
        assert (await client.post("/api/v1/web/customers/", json={})).status_code == 422

    async def test_non_integer_path_id_is_422(self, writer):
        assert (await writer.get("/api/v1/web/customers/not-a-number")).status_code == 422


# ── Read ──────────────────────────────────────────────────────────────


class TestRead:
    async def test_reads_back_a_created_customer(self, writer):
        created = (await writer.post("/api/v1/web/customers/", json=FULL_PAYLOAD)).json()

        response = await writer.get(f"/api/v1/web/customers/{created['id']}")

        assert response.status_code == 200
        assert response.json()["id"] == created["id"]
        assert response.json()["name"] == FULL_PAYLOAD["name"]

    async def test_unknown_id_is_404(self, writer):
        assert (await writer.get("/api/v1/web/customers/424242")).status_code == 404


# ── List / filter / paginate ──────────────────────────────────────────


class TestList:
    async def _seed(self, client, names):
        return [
            (await client.post("/api/v1/web/customers/", json={"name": n, "level": "A"})).json()
            for n in names
        ]

    async def test_empty_list_has_a_zero_total(self, writer):
        body = (await writer.get("/api/v1/web/customers/")).json()
        assert body["items"] == []
        assert body["total"] == 0

    async def test_lists_everything_created(self, writer):
        await self._seed(writer, ["Alpha", "Beta", "Gamma"])

        body = (await writer.get("/api/v1/web/customers/")).json()

        assert body["total"] == 3
        assert {i["name"] for i in body["items"]} == {"Alpha", "Beta", "Gamma"}

    async def test_limit_caps_the_page_but_not_the_total(self, writer):
        await self._seed(writer, ["Alpha", "Beta", "Gamma"])

        body = (await writer.get("/api/v1/web/customers/?limit=2")).json()

        assert len(body["items"]) == 2
        assert body["total"] == 3

    async def test_skip_offsets_the_page(self, writer):
        await self._seed(writer, ["Alpha", "Beta", "Gamma"])

        first = (await writer.get("/api/v1/web/customers/?limit=2")).json()
        second = (await writer.get("/api/v1/web/customers/?skip=2&limit=2")).json()

        assert len(second["items"]) == 1
        first_ids = {i["id"] for i in first["items"]}
        assert {i["id"] for i in second["items"]}.isdisjoint(first_ids)

    async def test_filters_by_id(self, writer):
        created = await self._seed(writer, ["Alpha", "Beta"])
        target = created[0]["id"]

        body = (await writer.get(f"/api/v1/web/customers/?id={target}")).json()

        assert [i["id"] for i in body["items"]] == [target]

    async def test_filters_by_level(self, writer):
        await writer.post("/api/v1/web/customers/", json={"name": "TierA", "level": "A"})
        await writer.post("/api/v1/web/customers/", json={"name": "TierC", "level": "C"})

        body = (await writer.get("/api/v1/web/customers/?level=C")).json()

        assert [i["name"] for i in body["items"]] == ["TierC"]

    async def test_isolation_between_tests(self, writer):
        """Guards the _clean_tables fixture itself: if table cleanup
        regressed, rows from the tests above would show up here and every
        count assertion in this file would become order-dependent."""
        assert (await writer.get("/api/v1/web/customers/")).json()["total"] == 0

    async def test_a_bare_request_does_not_return_the_whole_table(self, writer, db):
        """Regression guard: a list request with no `limit` must never
        mean "everything" (SQLAlchemy's Query.limit(None) is a no-op).
        Seeds directly via the ORM rather than one HTTP POST per row,
        this is a pagination-cap check, not a create-flow check, and 100+
        live requests per test would make the suite needlessly slow.
        `writer` is the only user created so far, so it is id=1."""
        now = (await writer.get("/api/v1/web/customers/")).json()  # sanity: table is empty first
        assert now["total"] == 0

        row_count = DEFAULT_PAGE_SIZE + 4
        db.add_all(
            CustomerOrmModel(
                name=f"Customer {i}", level="A", creator_id=1, created=datetime.now(UTC)
            )
            for i in range(row_count)
        )
        await db.commit()

        body = (await writer.get("/api/v1/web/customers/")).json()

        assert body["total"] == row_count
        assert len(body["items"]) == DEFAULT_PAGE_SIZE

    async def test_an_explicit_limit_above_the_max_is_rejected(self, writer):
        response = await writer.get(f"/api/v1/web/customers/?limit={MAX_PAGE_SIZE + 1}")

        assert response.status_code == 422


# ── Sort (one assertion per allow-listed order_by column) ──────────────


class TestSorting:
    async def _seed(self, client, names):
        return [
            (await client.post("/api/v1/web/customers/", json={"name": n, "level": "A"})).json()
            for n in names
        ]

    async def test_sorts_by_id_both_directions(self, writer):
        await self._seed(writer, ["Alpha", "Beta"])

        asc = (await writer.get("/api/v1/web/customers/?order_by=id&order_dir=asc")).json()
        ids = [i["id"] for i in asc["items"]]
        assert ids == sorted(ids)

        desc = (await writer.get("/api/v1/web/customers/?order_by=id&order_dir=desc")).json()
        ids = [i["id"] for i in desc["items"]]
        assert ids == sorted(ids, reverse=True)

    async def test_sorts_by_name_both_directions(self, writer):
        await self._seed(writer, ["Zeta", "Alpha"])

        asc = (await writer.get("/api/v1/web/customers/?order_by=name&order_dir=asc")).json()
        names = [i["name"] for i in asc["items"]]
        assert names == sorted(names)

        desc = (await writer.get("/api/v1/web/customers/?order_by=name&order_dir=desc")).json()
        names = [i["name"] for i in desc["items"]]
        assert names == sorted(names, reverse=True)

    async def test_sorts_by_created_both_directions(self, writer, db):
        created = await self._seed(writer, ["C1", "C2", "C3"])
        for offset, c in enumerate(created):
            await db.execute(
                update(CustomerOrmModel)
                .where(CustomerOrmModel.id == c["id"])
                .values({"created": datetime(2026, 1, 1 + offset, tzinfo=UTC)})
            )
        await db.commit()

        asc = (await writer.get("/api/v1/web/customers/?order_by=created&order_dir=asc")).json()
        dates = [i["created"] for i in asc["items"]]
        assert dates == sorted(dates)

        desc = (await writer.get("/api/v1/web/customers/?order_by=created&order_dir=desc")).json()
        dates = [i["created"] for i in desc["items"]]
        assert dates == sorted(dates, reverse=True)

    async def test_sorts_by_changed_both_directions(self, writer, db):
        created = await self._seed(writer, ["C1", "C2", "C3"])
        for offset, c in enumerate(created):
            await db.execute(
                update(CustomerOrmModel)
                .where(CustomerOrmModel.id == c["id"])
                .values({"changed": datetime(2026, 2, 1 + offset, tzinfo=UTC)})
            )
        await db.commit()

        asc = (await writer.get("/api/v1/web/customers/?order_by=changed&order_dir=asc")).json()
        dates = [i["changed"] for i in asc["items"]]
        assert dates == sorted(dates)

        desc = (await writer.get("/api/v1/web/customers/?order_by=changed&order_dir=desc")).json()
        dates = [i["changed"] for i in desc["items"]]
        assert dates == sorted(dates, reverse=True)


# ── Update ────────────────────────────────────────────────────────────


class TestUpdate:
    async def test_updates_persist_and_are_readable(self, writer):
        created = (await writer.post("/api/v1/web/customers/", json=FULL_PAYLOAD)).json()

        updated = await writer.put(
            f"/api/v1/web/customers/{created['id']}",
            json={
                **FULL_PAYLOAD,
                "expected_edit_version": await row_version(writer, f"/customers/{created['id']}"),
                "name": "Renamed",
                "level": "C",
            },
        )

        assert updated.status_code == 200
        assert updated.json()["name"] == "Renamed"

        reread = (await writer.get(f"/api/v1/web/customers/{created['id']}")).json()
        assert reread["name"] == "Renamed"
        assert reread["level"] == "C"

    async def test_update_keeps_the_same_id(self, writer):
        created = (await writer.post("/api/v1/web/customers/", json=FULL_PAYLOAD)).json()

        updated = (
            await writer.put(
                f"/api/v1/web/customers/{created['id']}",
                json={
                    **FULL_PAYLOAD,
                    "expected_edit_version": await row_version(
                        writer, f"/customers/{created['id']}"
                    ),
                    "name": "Renamed",
                },
            )
        ).json()

        assert updated["id"] == created["id"]

    async def test_update_does_not_create_a_second_row(self, writer):
        created = (await writer.post("/api/v1/web/customers/", json=FULL_PAYLOAD)).json()

        await writer.put(
            f"/api/v1/web/customers/{created['id']}",
            json={
                **FULL_PAYLOAD,
                "expected_edit_version": await row_version(writer, f"/customers/{created['id']}"),
                "name": "Renamed",
            },
        )

        assert (await writer.get("/api/v1/web/customers/")).json()["total"] == 1

    async def test_records_the_changing_user(self, writer, auth_client):
        created = (await writer.post("/api/v1/web/customers/", json=FULL_PAYLOAD)).json()
        editor = await auth_client(permissions=WRITE, username="editor", email="editor@example.com")

        updated = (
            await editor.put(
                f"/api/v1/web/customers/{created['id']}",
                json={
                    **FULL_PAYLOAD,
                    "expected_edit_version": await row_version(
                        editor, f"/customers/{created['id']}"
                    ),
                    "name": "Renamed",
                },
            )
        ).json()

        assert updated["creator_id"] == created["creator_id"]
        assert updated["changed_by_id"] not in (None, created["creator_id"])
        assert updated["changed_by"]["id"] == updated["changed_by_id"]
        reread = (await writer.get(f"/api/v1/web/customers/{created['id']}")).json()
        assert reread["changed_by_id"] == updated["changed_by_id"]

    async def test_a_change_outside_a_request_clears_the_changer(self, writer, db):
        created = (await writer.post("/api/v1/web/customers/", json=FULL_PAYLOAD)).json()
        await writer.put(
            f"/api/v1/web/customers/{created['id']}",
            json={
                **FULL_PAYLOAD,
                "expected_edit_version": await row_version(writer, f"/customers/{created['id']}"),
                "name": "Renamed",
            },
        )

        row = await db.get(CustomerOrmModel, created["id"])
        assert row is not None
        row.changed = datetime(2026, 5, 1, tzinfo=UTC)
        await db.commit()

        reread = (await writer.get(f"/api/v1/web/customers/{created['id']}")).json()
        assert reread["changed_by_id"] is None
        assert reread["changed_by"] is None


# ── Archive / Restore ───────────────────────────────────────────────
#
# Customers have no DELETE route: the MANAGE_PROJECTS gate guards
# POST /{id}/archive and POST /{id}/restore. Archiving
# is idempotent and hides a customer from the default list without
# removing the row; GET /{id} always resolves regardless of `archived`
# (a scanned/linked reference must still work), and archived rows may
# still be read, listed with `include_archived=true`, and even updated;
# nothing in the contract blocks editing an archived row, only creating a
# duplicate live one.


class TestArchiveRestore:
    async def test_archive_returns_200_and_hides_the_customer_from_the_default_list(self, manager):
        created = (await manager.post("/api/v1/web/customers/", json=FULL_PAYLOAD)).json()

        resp = await manager.post(f"/api/v1/web/customers/{created['id']}/archive")
        assert resp.status_code == 200
        assert resp.json()["archived"] is True

        assert (await manager.get("/api/v1/web/customers/")).json()["total"] == 0

    async def test_archive_is_soft_the_row_still_exists(self, manager, db):
        """ArchiveCustomer sets archived=True rather than removing the row."""
        created = (await manager.post("/api/v1/web/customers/", json=FULL_PAYLOAD)).json()

        await manager.post(f"/api/v1/web/customers/{created['id']}/archive")

        row = (
            await db.execute(
                text("SELECT archived FROM customer_table WHERE id = :id"), {"id": created["id"]}
            )
        ).one()
        assert bool(row[0]) is True

    async def test_archiving_twice_is_idempotent(self, manager):
        created = (await manager.post("/api/v1/web/customers/", json=FULL_PAYLOAD)).json()

        first = await manager.post(f"/api/v1/web/customers/{created['id']}/archive")
        second = await manager.post(f"/api/v1/web/customers/{created['id']}/archive")

        assert first.status_code == 200
        assert second.status_code == 200
        assert second.json()["archived"] is True

    async def test_archive_requires_manage_permission(self, writer):
        created = (await writer.post("/api/v1/web/customers/", json=FULL_PAYLOAD)).json()

        resp = await writer.post(f"/api/v1/web/customers/{created['id']}/archive")

        assert resp.status_code == 403

    async def test_archived_customer_still_readable_by_id(self, manager):
        created = (await manager.post("/api/v1/web/customers/", json=FULL_PAYLOAD)).json()

        await manager.post(f"/api/v1/web/customers/{created['id']}/archive")

        resp = await manager.get(f"/api/v1/web/customers/{created['id']}")
        assert resp.status_code == 200
        assert resp.json()["archived"] is True

    async def test_archived_customer_included_with_include_archived(self, manager):
        created = (await manager.post("/api/v1/web/customers/", json=FULL_PAYLOAD)).json()
        await manager.post(f"/api/v1/web/customers/{created['id']}/archive")

        default_list = (await manager.get("/api/v1/web/customers/")).json()
        assert created["id"] not in {i["id"] for i in default_list["items"]}

        included_list = (
            await manager.get("/api/v1/web/customers/", params={"include_archived": True})
        ).json()
        assert created["id"] in {i["id"] for i in included_list["items"]}

    async def test_archived_customer_can_still_be_updated(self, manager):
        created = (await manager.post("/api/v1/web/customers/", json=FULL_PAYLOAD)).json()

        await manager.post(f"/api/v1/web/customers/{created['id']}/archive")

        response = await manager.put(
            f"/api/v1/web/customers/{created['id']}",
            json={
                **FULL_PAYLOAD,
                "expected_edit_version": await row_version(manager, f"/customers/{created['id']}"),
                "name": "Resurrected",
            },
        )
        assert response.status_code == 200
        assert response.json()["name"] == "Resurrected"

    async def test_vat_id_is_released_when_a_customer_is_archived(self, manager):
        """Uniqueness is enforced by a partial index (WHERE archived IS
        false), so archiving a customer frees its VAT id for reuse instead
        of reserving it forever."""
        first = (await manager.post("/api/v1/web/customers/", json=FULL_PAYLOAD)).json()
        await manager.post(f"/api/v1/web/customers/{first['id']}/archive")

        response = await manager.post("/api/v1/web/customers/", json=FULL_PAYLOAD)

        assert response.status_code == 201
        assert response.json()["id"] != first["id"]

    async def test_vat_id_is_still_unique_among_live_customers(self, manager):
        """The relaxation must not go too far, two *active* customers
        still cannot share a VAT id."""
        await manager.post("/api/v1/web/customers/", json=FULL_PAYLOAD)

        response = await manager.post("/api/v1/web/customers/", json=FULL_PAYLOAD)

        assert response.status_code != 201
        assert response.status_code < 500

    async def test_archive_only_affects_the_targeted_row(self, manager):
        keep = (await manager.post("/api/v1/web/customers/", json={"name": "Keep"})).json()
        drop = (await manager.post("/api/v1/web/customers/", json={"name": "Drop"})).json()

        await manager.post(f"/api/v1/web/customers/{drop['id']}/archive")

        remaining = (await manager.get("/api/v1/web/customers/")).json()
        assert [i["id"] for i in remaining["items"]] == [keep["id"]]

    async def test_restore_returns_200_and_unhides_the_customer(self, manager):
        created = (await manager.post("/api/v1/web/customers/", json=FULL_PAYLOAD)).json()
        await manager.post(f"/api/v1/web/customers/{created['id']}/archive")

        resp = await manager.post(f"/api/v1/web/customers/{created['id']}/restore")
        assert resp.status_code == 200
        assert resp.json()["archived"] is False

        default_list = (await manager.get("/api/v1/web/customers/")).json()
        assert created["id"] in {i["id"] for i in default_list["items"]}

    async def test_restoring_twice_is_idempotent(self, manager):
        created = (await manager.post("/api/v1/web/customers/", json=FULL_PAYLOAD)).json()
        await manager.post(f"/api/v1/web/customers/{created['id']}/archive")
        await manager.post(f"/api/v1/web/customers/{created['id']}/restore")

        resp = await manager.post(f"/api/v1/web/customers/{created['id']}/restore")
        assert resp.status_code == 200
        assert resp.json()["archived"] is False

    async def test_restore_requires_manage_permission(self, writer, auth_client):
        manager = await auth_client(
            username="manager", email="manager@example.com", permissions=MANAGE
        )
        created = (await writer.post("/api/v1/web/customers/", json=FULL_PAYLOAD)).json()
        await manager.post(f"/api/v1/web/customers/{created['id']}/archive")

        resp = await writer.post(f"/api/v1/web/customers/{created['id']}/restore")

        assert resp.status_code == 403

    async def test_restore_conflicts_on_vat_id_already_taken_by_a_live_customer(self, manager):
        archived = (await manager.post("/api/v1/web/customers/", json=FULL_PAYLOAD)).json()
        await manager.post(f"/api/v1/web/customers/{archived['id']}/archive")
        # A new, live customer now legitimately claims the same VAT id,
        # since the partial unique index only guards live rows.
        await manager.post("/api/v1/web/customers/", json=FULL_PAYLOAD)

        resp = await manager.post(f"/api/v1/web/customers/{archived['id']}/restore")

        assert resp.status_code == 409
        assert resp.json()["code"] == "CustomerAlreadyExistsError"

    async def test_not_found_archive_is_404(self, manager):
        assert (await manager.post("/api/v1/web/customers/424242/archive")).status_code == 404

    async def test_not_found_restore_is_404(self, manager):
        assert (await manager.post("/api/v1/web/customers/424242/restore")).status_code == 404


# ── Column filters ────────────────────────────────────────────────────


class TestColumnFilters:
    """Each management-table row filter, one match and one miss."""

    @staticmethod
    async def _create(client, name, **fields):
        resp = await client.post("/api/v1/web/customers/", json={"name": name} | fields)
        assert resp.status_code == 201, resp.text
        return resp.json()

    @staticmethod
    async def _ids(client, query):
        resp = await client.get(f"/api/v1/web/customers/?{query}")
        assert resp.status_code == 200, resp.text
        return {i["id"] for i in resp.json()["items"]}

    async def test_filters_by_legal_name_substring(self, writer):
        hit = await self._create(writer, "Alpha", legal_name="Alpha Holding Ltd")
        await self._create(writer, "Beta", legal_name="Beta plc")

        assert await self._ids(writer, "legal_name=holding") == {hit["id"]}
        assert await self._ids(writer, "legal_name=nomatch") == set()

    async def test_filters_by_address_across_street_postal_code_and_city(self, writer):
        by_street = await self._create(writer, "Alpha", street="Highfield Road 1")
        by_postal = await self._create(writer, "Beta", postal_code="4020")
        by_city = await self._create(writer, "Gamma", city="Leeds")
        await self._create(writer, "Delta", street="Ring Road 2", postal_code="1010", city="London")

        assert await self._ids(writer, "address=highfield") == {by_street["id"]}
        assert await self._ids(writer, "address=402") == {by_postal["id"]}
        assert await self._ids(writer, "address=leeds") == {by_city["id"]}
        assert await self._ids(writer, "address=york") == set()

    async def test_filters_by_country_substring(self, writer):
        hit = await self._create(writer, "Alpha", country="AT")
        await self._create(writer, "Beta", country="DE")

        assert await self._ids(writer, "country=at") == {hit["id"]}
        assert await self._ids(writer, "country=CH") == set()

    async def test_filters_by_email_substring(self, writer):
        hit = await self._create(writer, "Alpha", email="sales@alpha.example")
        await self._create(writer, "Beta", email="info@beta.example")

        assert await self._ids(writer, "email=alpha") == {hit["id"]}
        assert await self._ids(writer, "email=gamma") == set()

    async def test_filters_by_creator(self, writer):
        hit = await self._create(writer, "Alpha")

        assert await self._ids(writer, f"creator_id={hit['creator_id']}") == {hit["id"]}
        assert await self._ids(writer, f"creator_id={hit['creator_id'] + 999}") == set()

    async def test_filters_by_changer(self, writer):
        hit = await self._create(writer, "Alpha")
        await self._create(writer, "Beta")
        await writer.put(
            f"/api/v1/web/customers/{hit['id']}",
            json={
                **FULL_PAYLOAD,
                "expected_edit_version": await row_version(writer, f"/customers/{hit['id']}"),
                "name": "Alpha",
            },
        )

        assert await self._ids(writer, f"changed_by_id={hit['creator_id']}") == {hit["id"]}
        assert await self._ids(writer, f"changed_by_id={hit['creator_id'] + 999}") == set()

    async def test_created_bounds_are_inclusive(self, writer, db):
        hit = await self._create(writer, "Alpha")
        other = await self._create(writer, "Beta")
        await db.execute(
            update(CustomerOrmModel)
            .where(CustomerOrmModel.id == hit["id"])
            # 23:30 on 10 March in Vienna, the tenant's timezone (CET).
            .values({"created": datetime(2026, 3, 10, 22, 30, tzinfo=UTC)})
        )
        await db.execute(
            update(CustomerOrmModel)
            .where(CustomerOrmModel.id == other["id"])
            .values({"created": datetime(2026, 3, 20, tzinfo=UTC)})
        )
        await db.commit()

        assert await self._ids(writer, "created_from=2026-03-10&created_to=2026-03-10") == {
            hit["id"]
        }
        assert await self._ids(writer, "created_from=2026-03-11&created_to=2026-03-19") == set()

    async def test_changed_bounds_are_inclusive(self, writer, db):
        hit = await self._create(writer, "Alpha")
        other = await self._create(writer, "Beta")
        await db.execute(
            update(CustomerOrmModel)
            .where(CustomerOrmModel.id == hit["id"])
            # 23:30 on 10 April in Vienna, the tenant's timezone (CEST).
            .values({"changed": datetime(2026, 4, 10, 21, 30, tzinfo=UTC)})
        )
        await db.execute(
            update(CustomerOrmModel)
            .where(CustomerOrmModel.id == other["id"])
            .values({"changed": datetime(2026, 4, 20, tzinfo=UTC)})
        )
        await db.commit()

        assert await self._ids(writer, "changed_from=2026-04-10&changed_to=2026-04-10") == {
            hit["id"]
        }
        assert await self._ids(writer, "changed_from=2026-04-11&changed_to=2026-04-19") == set()
