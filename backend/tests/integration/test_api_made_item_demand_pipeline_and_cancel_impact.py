"""
HTTP-level coverage for two made-item demand routes with no prior
integration test:

  - GET /api/v1/web/made-items-demands/pipeline (GetDemandsPipeline)
  - GET /api/v1/web/made-items-demands/{demand_id}/cancel-impact
    (PreviewCancelMadeItemDemand)

Both are open to any authenticated user (no permission check in the
endpoint or the use case), so "permission check" here means confirming
that an unauthenticated caller is rejected and an ordinary authenticated
one is accepted, since there is nothing more specific to gate on.

The pipeline route's use case (GetDemandsPipeline) already has full unit
coverage (tests/unit/test_made_item_demand_use_cases.py::TestGetDemandsPipeline),
but that unit test fakes the repository outright, so it never exercises the
real SQL predicate in SqlAlchemyMadeItemDemandItemRepository.get_pipeline
(in-flight statuses always included; terminal statuses only when `changed`
is on/after `terminal_since`). That predicate is what this file's data case
actually proves.
"""

from datetime import UTC
from datetime import date
from datetime import datetime
from datetime import timedelta

from src.modules.catalogue.adapters.outbound.persistence.repositories.made_item_repository.item import (
    SqlAlchemyMadeItemRepository,
)
from src.modules.catalogue.domain.entities.made_item import MadeItem
from src.modules.catalogue.domain.value_objects.data_source import DataSource
from src.modules.catalogue.domain.value_objects.made_item_status import MadeItemCatalogueStatus
from src.modules.catalogue.domain.value_objects.made_item_status import MadeItemDemandStatus
from src.modules.fulfillment.adapters.outbound.persistence.repositories.made_item_demand_repository.demand_item import (
    SqlAlchemyMadeItemDemandItemRepository,
)
from src.modules.fulfillment.domain.entities.made_item_demand_item import MadeItemDemandItem
from src.modules.workspace.adapters.outbound.persistence.repositories.project_repository import (
    SqlAlchemyProjectRepository,
)
from src.modules.workspace.domain.entities.project import Project

PIPELINE_URL = "/api/v1/web/made-items-demands/pipeline"


async def _project(db, creator_id: int, number: str = "P-001") -> int:
    project = await SqlAlchemyProjectRepository(db).save(
        Project(id=0, created=datetime.now(UTC), creator_id=creator_id, project_number=number)
    )
    return project.id


async def _made_item(db, creator_id: int, part_number: str = "PN-001", revision: str = "0") -> int:
    item = await SqlAlchemyMadeItemRepository(db).save(
        MadeItem(
            id=0,
            created=datetime.now(UTC),
            changed=datetime.now(UTC),
            changes=[],
            archived=False,
            revision=revision,
            revision_date=None,
            revision_note=None,
            article_name="Pipeline Part",
            status=MadeItemCatalogueStatus.ACTIVE,
            data_source=DataSource.WEB,
            part_number=part_number,
            material=None,
            mass=None,
            base_size=None,
            note=None,
            weblink=None,
            files=[],
            creator_id=creator_id,
            approver_id=None,
            bought_item_id=None,
            source_item_id=None,
            article_group_ids=[],
            successor_item_id=None,
            changed_by_id=None,
        )
    )
    await db.commit()
    return item.id


async def _demand(
    db,
    project_id: int,
    made_item_id: int,
    creator_id: int,
    status: MadeItemDemandStatus = MadeItemDemandStatus.OPEN,
    changed: date | None = None,
) -> int:
    demand = await SqlAlchemyMadeItemDemandItemRepository(db).save(
        MadeItemDemandItem(
            id=0,
            created=date(2026, 1, 1),
            changed=changed,
            changes=[],
            status=status,
            quantity=5.0,
            unit="pcs",
            items_per_unit=1.0,
            high_priority=False,
            notify_on_delivery=False,
            note=None,
            desired_delivery_date=None,
            creator_id=creator_id,
            made_item_id=made_item_id,
            project_id=project_id,
            # A canceled demand records the intent its status stands for.
            canceled_at=datetime(2026, 1, 2, tzinfo=UTC) if status == "canceled" else None,
        )
    )
    await db.commit()
    return demand.id


class TestPipelineAuth:
    async def test_requires_authentication(self, client):
        assert (await client.get(PIPELINE_URL)).status_code == 401

    async def test_any_authenticated_user_may_read_it(self, auth_client):
        client = await auth_client(permissions=[])

        response = await client.get(PIPELINE_URL)

        assert response.status_code == 200
        assert response.json() == {"items": []}


class TestPipelineData:
    async def test_in_flight_always_shown_terminal_only_when_recent(self, auth_client, db):
        client = await auth_client(permissions=[])
        me = (await client.get("/api/v1/web/users/me")).json()
        project_id = await _project(db, me["id"])
        item_id = await _made_item(db, me["id"])

        open_id = await _demand(db, project_id, item_id, me["id"], status=MadeItemDemandStatus.OPEN)
        recent_cutoff = date(2026, 6, 1)
        stale_canceled_id = await _demand(
            db,
            project_id,
            item_id,
            me["id"],
            status=MadeItemDemandStatus.CANCELED,
            changed=recent_cutoff - timedelta(days=10),
        )
        fresh_canceled_id = await _demand(
            db,
            project_id,
            item_id,
            me["id"],
            status=MadeItemDemandStatus.CANCELED,
            changed=recent_cutoff,
        )

        response = await client.get(
            PIPELINE_URL, params={"terminal_since": recent_cutoff.isoformat()}
        )

        assert response.status_code == 200
        rows = response.json()["items"]
        ids = {row["demand_item_id"] for row in rows}
        assert open_id in ids
        assert fresh_canceled_id in ids
        assert stale_canceled_id not in ids

        open_row = next(r for r in rows if r["demand_item_id"] == open_id)
        assert open_row["item_part_number"] == "PN-001"
        assert open_row["project_id"] == project_id
        assert open_row["unit"] == "pcs"
        assert open_row["total"] == 5.0


class TestCancelImpactAuth:
    async def test_requires_authentication(self, client):
        # No seeding needed: auth is rejected before any demand lookup runs.
        assert (
            await client.get("/api/v1/web/made-items-demands/1/cancel-impact")
        ).status_code == 401


class TestCancelImpactData:
    async def test_unknown_demand_is_404(self, auth_client):
        client = await auth_client(permissions=[])

        response = await client.get("/api/v1/web/made-items-demands/999999/cancel-impact")

        assert response.status_code == 404

    async def test_demand_with_no_lot_allocations_reports_nothing_to_cancel(self, auth_client, db):
        client = await auth_client(permissions=[])
        me = (await client.get("/api/v1/web/users/me")).json()
        project_id = await _project(db, me["id"], number="P-002")
        item_id = await _made_item(db, me["id"], part_number="PN-002")
        demand_id = await _demand(
            db, project_id, item_id, me["id"], status=MadeItemDemandStatus.OPEN
        )

        response = await client.get(f"/api/v1/web/made-items-demands/{demand_id}/cancel-impact")

        assert response.status_code == 200
        body = response.json()
        assert body["demand_item_id"] == demand_id
        assert body["status"] == "open"
        assert body["item_part_number"] == "PN-002"
        assert body["lots"] == []
        # No lots at all means nothing would be force-canceled, so this is
        # allowed regardless of the actor's manage:lots permission (see
        # CancelImpactCollector.collect: `not any(...)` over an empty list).
        assert body["can_cancel_lots"] is True
