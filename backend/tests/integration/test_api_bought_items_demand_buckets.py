"""
CRUD + permissions coverage for the bought-item demand bucket aggregate
(`/api/v1/web/bought-items-demand-buckets`, `auth_client(permissions=...)`
pattern per test_api_article_groups_pagination.py's template), plus the
two demand-side integration points: filtering the bought-item demand
list by bucket_id/include_unbucketed, and deleting a bucket nulling
`bucket_id` on every demand it was assigned to.
"""

from datetime import UTC
from datetime import date
from datetime import datetime

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.modules.catalogue.domain.value_objects.bought_item_status import BoughtItemDemandStatus
from src.modules.fulfillment.adapters.outbound.persistence.models.bought_item_demand_item_model import (
    BoughtItemDemandItemOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.bought_item_repository.demand_item import (
    SqlAlchemyBoughtItemDemandItemRepository,
)
from src.modules.fulfillment.domain.entities.bought_item_demand_item import BoughtItemDemandItem
from src.modules.platform.domain.value_objects.permission import Permission
from src.modules.workspace.adapters.outbound.persistence.repositories.project_repository import (
    SqlAlchemyProjectRepository,
)
from src.modules.workspace.domain.entities.project import Project

WRITE = [Permission.WRITE_DEMAND_ITEMS]
BUCKETS_URL = "/api/v1/web/bought-items-demand-buckets/"


@pytest.fixture
async def writer(auth_client):
    return await auth_client(permissions=WRITE)


@pytest.fixture
async def reader(auth_client):
    # Distinct username/email from `writer` (its default "tester"/
    # "tester@example.com"): tests that need both fixtures at once would
    # otherwise hit a UNIQUE constraint creating this second user.
    return await auth_client(username="reader", email="reader@example.com", permissions=[])


async def _create(client, name="Urgent", **overrides):
    body = {"name": name, "color": "#ff0000"} | overrides
    resp = await client.post(BUCKETS_URL, json=body)
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _project(db: Session, creator_id: int = 1, number: str = "P-001") -> int:
    project = await SqlAlchemyProjectRepository(db).save(
        Project(id=0, created=datetime.now(UTC), creator_id=creator_id, project_number=number)
    )
    return project.id


async def _demand(
    db: Session, project_id: int, creator_id: int = 1, bucket_id: int | None = None
) -> int:
    demand = await SqlAlchemyBoughtItemDemandItemRepository(db).save(
        BoughtItemDemandItem(
            id=0,
            created=date.today(),
            changed=None,
            changes=[],
            status=BoughtItemDemandStatus.OPEN,
            quantity=5.0,
            unit="pcs",
            items_per_unit=1.0,
            high_priority=False,
            notify_on_delivery=False,
            note=None,
            desired_delivery_date=None,
            creator_id=creator_id,
            item_id=1,
            project_id=project_id,
            bucket_id=bucket_id,
        )
    )
    await db.commit()
    return demand.id


class TestBucketCrud:
    async def test_create_bucket(self, writer):
        body = await _create(writer, name="Urgent")
        assert body["name"] == "Urgent"
        assert body["color"] == "#ff0000"
        assert body["id"] > 0
        assert "creator_id" in body

    async def test_create_requires_permission(self, reader):
        resp = await reader.post(BUCKETS_URL, json={"name": "Nope", "color": "#ff0000"})
        assert resp.status_code == 403

    async def test_create_duplicate_name_conflicts(self, writer):
        await _create(writer, name="Urgent")
        resp = await writer.post(BUCKETS_URL, json={"name": "Urgent", "color": "#00ff00"})
        assert resp.status_code == 409

    async def test_create_duplicate_name_is_case_insensitive(self, writer):
        await _create(writer, name="Urgent")
        resp = await writer.post(BUCKETS_URL, json={"name": "URGENT", "color": "#00ff00"})
        assert resp.status_code == 409

    async def test_create_invalid_color_rejected(self, writer):
        resp = await writer.post(BUCKETS_URL, json={"name": "Urgent", "color": "red"})
        assert resp.status_code == 422

    async def test_list_buckets(self, writer):
        await _create(writer, name="Alpha")
        await _create(writer, name="Beta")

        body = (await writer.get(BUCKETS_URL)).json()

        assert body["total"] == 2

    async def test_list_buckets_search(self, writer):
        await _create(writer, name="Alpha")
        await _create(writer, name="Beta")

        body = (await writer.get(f"{BUCKETS_URL}?search=alp")).json()

        assert body["total"] == 1
        assert body["items"][0]["name"] == "Alpha"

    async def test_update_bucket(self, writer):
        created = await _create(writer, name="Urgent")
        resp = await writer.put(
            f"{BUCKETS_URL}{created['id']}", json={"name": "Later", "color": "#00ff00"}
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["name"] == "Later"
        assert resp.json()["color"] == "#00ff00"

    async def test_update_is_persisted(self, writer):
        """Reads the edit back through a separate request, so an update that
        is never committed fails here."""
        created = await _create(writer, name="Urgent")
        resp = await writer.put(
            f"{BUCKETS_URL}{created['id']}", json={"name": "Later", "color": "#00ff00"}
        )
        assert resp.status_code == 200, resp.text

        listing = (await writer.get(BUCKETS_URL)).json()
        assert [(b["name"], b["color"]) for b in listing["items"]] == [("Later", "#00ff00")]

    async def test_update_requires_permission(self, writer, reader):
        created = await _create(writer, name="Urgent")
        resp = await reader.put(
            f"{BUCKETS_URL}{created['id']}", json={"name": "Later", "color": "#00ff00"}
        )
        assert resp.status_code == 403

    async def test_update_not_found(self, writer):
        resp = await writer.put(f"{BUCKETS_URL}999999", json={"name": "Later", "color": "#00ff00"})
        assert resp.status_code == 404

    async def test_delete_bucket(self, writer):
        created = await _create(writer, name="Urgent")
        resp = await writer.delete(f"{BUCKETS_URL}{created['id']}")
        assert resp.status_code == 200, resp.text

        listing = (await writer.get(BUCKETS_URL)).json()
        assert listing["total"] == 0

    async def test_delete_requires_permission(self, writer, reader):
        created = await _create(writer, name="Urgent")
        resp = await reader.delete(f"{BUCKETS_URL}{created['id']}")
        assert resp.status_code == 403

    async def test_delete_not_found(self, writer):
        resp = await writer.delete(f"{BUCKETS_URL}999999")
        assert resp.status_code == 404


class TestDemandBucketAssignment:
    async def test_assigns_bucket(self, writer, db):
        project_id = await _project(db)
        demand_id = await _demand(db, project_id)
        bucket = await _create(writer, name="Urgent")

        resp = await writer.put(
            f"/api/v1/web/bought-items-demands/{demand_id}/bucket",
            json={"bucket_id": bucket["id"]},
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["bucket_id"] == bucket["id"]

    async def test_clears_bucket(self, writer, db):
        bucket = await _create(writer, name="Urgent")
        project_id = await _project(db)
        demand_id = await _demand(db, project_id, bucket_id=bucket["id"])

        resp = await writer.put(
            f"/api/v1/web/bought-items-demands/{demand_id}/bucket", json={"bucket_id": None}
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["bucket_id"] is None

    async def test_demand_not_found(self, writer):
        bucket = await _create(writer, name="Urgent")
        resp = await writer.put(
            "/api/v1/web/bought-items-demands/999999/bucket", json={"bucket_id": bucket["id"]}
        )
        assert resp.status_code == 404

    async def test_bucket_not_found(self, writer, db):
        project_id = await _project(db)
        demand_id = await _demand(db, project_id)
        resp = await writer.put(
            f"/api/v1/web/bought-items-demands/{demand_id}/bucket", json={"bucket_id": 999999}
        )
        assert resp.status_code == 404

    async def test_requires_permission(self, writer, reader, db):
        project_id = await _project(db)
        demand_id = await _demand(db, project_id)
        bucket = await _create(writer, name="Urgent")

        resp = await reader.put(
            f"/api/v1/web/bought-items-demands/{demand_id}/bucket",
            json={"bucket_id": bucket["id"]},
        )
        assert resp.status_code == 403

    async def test_does_not_touch_the_changelog(self, writer, db):
        project_id = await _project(db)
        demand_id = await _demand(db, project_id)
        bucket = await _create(writer, name="Urgent")

        before = (
            await writer.get(f"/api/v1/web/bought-items-demands/{demand_id}/changelog")
        ).json()
        await writer.put(
            f"/api/v1/web/bought-items-demands/{demand_id}/bucket",
            json={"bucket_id": bucket["id"]},
        )
        after = (await writer.get(f"/api/v1/web/bought-items-demands/{demand_id}/changelog")).json()

        assert before == after


class TestDemandListBucketFilter:
    async def test_no_filter_returns_everything(self, writer, db):
        project_id = await _project(db)
        await _demand(db, project_id)
        await _demand(db, project_id)

        body = (await writer.get("/api/v1/web/bought-items-demands/")).json()
        assert body["total"] == 2

    async def test_filters_by_a_single_bucket_id(self, writer, db):
        bucket_a = await _create(writer, name="A")
        bucket_b = await _create(writer, name="B")
        project_id = await _project(db)
        in_a = await _demand(db, project_id, bucket_id=bucket_a["id"])
        await _demand(db, project_id, bucket_id=bucket_b["id"])
        await _demand(db, project_id)

        body = (
            await writer.get(f"/api/v1/web/bought-items-demands/?bucket_id={bucket_a['id']}")
        ).json()

        assert body["total"] == 1
        assert body["items"][0]["id"] == in_a

    async def test_filters_by_multiple_bucket_ids(self, writer, db):
        bucket_a = await _create(writer, name="A")
        bucket_b = await _create(writer, name="B")
        project_id = await _project(db)
        await _demand(db, project_id, bucket_id=bucket_a["id"])
        await _demand(db, project_id, bucket_id=bucket_b["id"])
        await _demand(db, project_id)

        body = (
            await writer.get(
                f"/api/v1/web/bought-items-demands/?bucket_id={bucket_a['id']}"
                f"&bucket_id={bucket_b['id']}"
            )
        ).json()

        assert body["total"] == 2

    async def test_include_unbucketed(self, writer, db):
        bucket_a = await _create(writer, name="A")
        project_id = await _project(db)
        await _demand(db, project_id, bucket_id=bucket_a["id"])
        await _demand(db, project_id)
        await _demand(db, project_id)

        body = (
            await writer.get("/api/v1/web/bought-items-demands/?include_unbucketed=true")
        ).json()

        assert body["total"] == 2

    async def test_bucket_id_and_include_unbucketed_combined(self, writer, db):
        bucket_a = await _create(writer, name="A")
        bucket_b = await _create(writer, name="B")
        project_id = await _project(db)
        await _demand(db, project_id, bucket_id=bucket_a["id"])
        await _demand(db, project_id, bucket_id=bucket_b["id"])
        await _demand(db, project_id)

        body = (
            await writer.get(
                f"/api/v1/web/bought-items-demands/?bucket_id={bucket_a['id']}&include_unbucketed=true"
            )
        ).json()

        assert body["total"] == 2

    async def test_sorts_by_bucket_name_with_nulls_last(self, writer, db):
        bucket_z = await _create(writer, name="Zeta")
        bucket_a = await _create(writer, name="Alpha")
        project_id = await _project(db)
        unbucketed_id = await _demand(db, project_id)
        z_id = await _demand(db, project_id, bucket_id=bucket_z["id"])
        a_id = await _demand(db, project_id, bucket_id=bucket_a["id"])

        asc = (
            await writer.get("/api/v1/web/bought-items-demands/?order_by=bucket_name&order_dir=asc")
        ).json()
        asc_ids = [i["id"] for i in asc["items"]]
        assert asc_ids == [a_id, z_id, unbucketed_id]

        desc = (
            await writer.get(
                "/api/v1/web/bought-items-demands/?order_by=bucket_name&order_dir=desc"
            )
        ).json()
        desc_ids = [i["id"] for i in desc["items"]]
        assert desc_ids == [z_id, a_id, unbucketed_id]


class TestBucketDeleteNullsDemandBucketId:
    async def test_delete_nulls_bucket_id_on_every_assigned_demand(self, writer, db):
        bucket = await _create(writer, name="Urgent")
        project_id = await _project(db)
        d1 = await _demand(db, project_id, bucket_id=bucket["id"])
        d2 = await _demand(db, project_id, bucket_id=bucket["id"])
        other_bucket = await _create(writer, name="Other")
        d3 = await _demand(db, project_id, bucket_id=other_bucket["id"])

        resp = await writer.delete(f"{BUCKETS_URL}{bucket['id']}")
        assert resp.status_code == 200, resp.text

        for demand_id in (d1, d2):
            body = (await writer.get(f"/api/v1/web/bought-items-demands/{demand_id}")).json()
            assert body["bucket_id"] is None

        untouched = (await writer.get(f"/api/v1/web/bought-items-demands/{d3}")).json()
        assert untouched["bucket_id"] == other_bucket["id"]

    async def test_delete_moves_the_version_of_every_cleared_demand(self, writer, db):
        """The demands are cleared through the ORM, so a stale copy saved
        afterwards fails its version check instead of writing back a bucket
        that no longer exists."""
        bucket = await _create(writer, name="Urgent")
        project_id = await _project(db)
        demand_id = await _demand(db, project_id, bucket_id=bucket["id"])
        await db.commit()
        version_before = await db.scalar(
            select(BoughtItemDemandItemOrmModel.version).where(
                BoughtItemDemandItemOrmModel.id == demand_id
            )
        )

        resp = await writer.delete(f"{BUCKETS_URL}{bucket['id']}")
        assert resp.status_code == 200, resp.text

        db.expire_all()
        version_after = await db.scalar(
            select(BoughtItemDemandItemOrmModel.version).where(
                BoughtItemDemandItemOrmModel.id == demand_id
            )
        )
        assert version_after == version_before + 1
