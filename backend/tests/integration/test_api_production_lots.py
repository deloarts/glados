"""
HTTP-level coverage of /api/v1/web/production-lots, the other core
production aggregate. Prerequisites (project, made
item) are seeded through the real repositories; the lot itself is created
through the router under test (POST /), matching how a real client would
exercise it, since CreateLot needs no more setup than a made item + a
project.
"""

from datetime import UTC
from datetime import datetime

import pytest
from sqlalchemy.orm import Session

from src.bootstrap.adapters.outbound.persistence.repositories.admin_settings_repository import (
    SqlAlchemyAdminSettingsRepository,
)
from src.modules.catalogue.adapters.outbound.persistence.repositories.made_item_repository.item import (
    SqlAlchemyMadeItemRepository,
)
from src.modules.catalogue.domain.entities.admin_settings.made_items import AdminMadeItemSettings
from src.modules.catalogue.domain.entities.made_item import MadeItem
from src.modules.catalogue.domain.policies.item_field_ownership import default_policy
from src.modules.catalogue.domain.value_objects.data_source import DataSource
from src.modules.catalogue.domain.value_objects.made_item_status import MadeItemCatalogueStatus
from src.modules.fulfillment.adapters.outbound.persistence.repositories.production_lot_repository.lot import (
    SqlAlchemyProductionLotRepository,
)
from src.modules.fulfillment.domain.entities.admin_settings.production import (
    AdminProductionSettings,
)
from src.modules.fulfillment.domain.entities.lot_position import LotPosition
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionKind
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionStatus
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.value_objects.permission import Permission
from src.modules.workspace.adapters.outbound.persistence.repositories.project_repository import (
    SqlAlchemyProjectRepository,
)
from src.modules.workspace.domain.entities.project import Project
from tests.integration.conftest import auth_headers

BASE = "/api/v1/web/production-lots"


@pytest.fixture(autouse=True)
async def _seed_settings(db: Session) -> None:
    """CreateLot reads both the made-items (lot numbering) and production
    (order numbering / QA defaults) admin-settings domains; neither is in
    `_seed_admin_settings` (conftest.py). Mirrors InitDatabase's defaults."""
    repo = SqlAlchemyAdminSettingsRepository(db)
    await repo.save_made_items(
        AdminMadeItemSettings(
            id=1,
            item_number_format="FAB-{yy}-{seq:05d}",
            lot_number_format="LOT-{yy}-{seq:05d}",
            part_number_auto=True,
            part_number_editable=False,
            revision_start="0",
            revision_separator=":",
            revision_skip_ambiguous_letters=False,
            revision_only_newest_editable=True,
            revision_predecessor_status_web="ask",
            revision_predecessor_status_pdm="replaced",
            revision_field_policy=default_policy(),
            web_creation_allowed=True,
            pdm_part_number_pattern="",
        )
    )
    await db.commit()
    await repo.save_production(
        AdminProductionSettings(
            id=1,
            production_order_number_format="PON-{yy}-{seq:05d}",
            default_weekly_hours={0: 480, 1: 480, 2: 480, 3: 480, 4: 480, 5: 0, 6: 0},
            default_external_lead_days=0,
            response_time_days=1,
            require_qa=False,
        )
    )
    await db.commit()


@pytest.fixture
async def made_item_and_project(db: Session, owner: User) -> tuple[int, int]:
    project = await SqlAlchemyProjectRepository(db).save(
        Project(id=0, created=datetime.now(UTC), creator_id=owner.id, project_number="P-LOT-1")
    )
    made_item = await SqlAlchemyMadeItemRepository(db).save(
        MadeItem(
            id=0,
            created=datetime.now(UTC),
            changed=datetime.now(UTC),
            changes=[],
            archived=False,
            revision="0",
            revision_date=None,
            revision_note=None,
            article_name="Lot surface part",
            status=MadeItemCatalogueStatus.ACTIVE,
            data_source=DataSource.WEB,
            part_number=None,
            material=None,
            mass=None,
            base_size=None,
            note=None,
            weblink=None,
            files=[],
            creator_id=owner.id,
            approver_id=None,
            bought_item_id=None,
            source_item_id=None,
            article_group_ids=[],
            successor_item_id=None,
            changed_by_id=None,
        )
    )
    await db.commit()
    return made_item.id, project.id


@pytest.fixture
async def owner(create_user) -> User:
    return await create_user(username="lot-owner", email="lot-owner@example.com")


async def _create_lot(
    client,
    made_item_id: int,
    project_id: int,
    *,
    headers: dict[str, str] | None = None,
    **body_overrides: object,
) -> dict:
    body = {
        "made_item_id": made_item_id,
        "project_id": project_id,
        "quantity": 10.0,
    } | body_overrides
    resp = await client.post(f"{BASE}/", json=body, headers=headers)
    assert resp.status_code == 201, resp.text
    return resp.json()


async def test_create_lot_requires_write_permission(
    auth_client, made_item_and_project: tuple[int, int]
) -> None:
    made_item_id, project_id = made_item_and_project
    client = await auth_client(permissions=[])
    resp = await client.post(
        f"{BASE}/", json={"made_item_id": made_item_id, "project_id": project_id, "quantity": 5.0}
    )
    assert resp.status_code == 403


async def test_create_lot_rejects_bad_quantity(
    auth_client, made_item_and_project: tuple[int, int]
) -> None:
    made_item_id, project_id = made_item_and_project
    client = await auth_client(permissions=[Permission.WRITE_LOTS])
    resp = await client.post(
        f"{BASE}/", json={"made_item_id": made_item_id, "project_id": project_id, "quantity": 0}
    )
    assert resp.status_code == 422


@pytest.mark.smoke
async def test_create_and_read_lot(auth_client, made_item_and_project: tuple[int, int]) -> None:
    made_item_id, project_id = made_item_and_project
    client = await auth_client(permissions=[Permission.WRITE_LOTS])
    created = await _create_lot(client, made_item_id, project_id)
    resp = await client.get(f"{BASE}/{created['id']}")
    assert resp.status_code == 200
    assert resp.json()["quantity"] == 10.0


async def test_read_missing_lot_404(auth_client) -> None:
    client = await auth_client(permissions=[])
    resp = await client.get(f"{BASE}/999999")
    assert resp.status_code == 404


async def test_list_lots(auth_client, made_item_and_project: tuple[int, int]) -> None:
    made_item_id, project_id = made_item_and_project
    client = await auth_client(permissions=[Permission.WRITE_LOTS])
    await _create_lot(client, made_item_id, project_id)
    resp = await client.get(f"{BASE}/")
    assert resp.status_code == 200
    assert resp.json()["total"] >= 1


async def test_hold_a_draft_lot_is_an_invalid_transition(
    auth_client, made_item_and_project: tuple[int, int]
) -> None:
    """A freshly-created lot is DRAFT, which the lot intent table does not
    hold (see LOT_INTENTS in lifecycle/intents.py). ON_HOLD needs an
    already-scheduled lot, out of proportion to seed here.
    This still proves the route, permission check and status-transition
    guard all resolve correctly over HTTP."""
    made_item_id, project_id = made_item_and_project
    client = await auth_client(permissions=[Permission.WRITE_LOTS])
    created = await _create_lot(client, made_item_id, project_id)

    resp = await client.post(f"{BASE}/{created['id']}/hold", json={"reason": "Waiting on tooling."})
    assert resp.status_code == 422


async def test_cancel_lot_requires_manage_permission(
    client, create_user, made_item_and_project: tuple[int, int]
) -> None:
    """CancelLot forces a cascade into every child position/order/order
    item (see lot_lifecycle.py's _assert_can_force_status), so, unlike
    production-orders' own creator-or-manage cancel gate, it requires
    manage:lots outright; being the lot's own creator is not enough."""
    made_item_id, project_id = made_item_and_project
    creator = await create_user(
        username="lot-creator", email="lot-creator@example.com", permissions=[Permission.WRITE_LOTS]
    )
    created = await _create_lot(
        client, made_item_id, project_id, headers=await auth_headers(creator)
    )

    resp = await client.post(
        f"{BASE}/{created['id']}/cancel",
        json={"expected_edit_version": created["edit_version"]},
        headers=await auth_headers(creator),
    )
    assert resp.status_code == 403

    # manage:lots comes on top of the base permission write:lots, as for
    # every other lot action.
    manage_only = await create_user(
        username="lot-manage-only",
        email="lot-manage-only@example.com",
        permissions=[Permission.MANAGE_LOTS],
    )
    resp = await client.post(
        f"{BASE}/{created['id']}/cancel",
        json={"expected_edit_version": created["edit_version"]},
        headers=await auth_headers(manage_only),
    )
    assert resp.status_code == 403

    manager = await create_user(
        username="lot-manager",
        email="lot-manager@example.com",
        permissions=[Permission.WRITE_LOTS, Permission.MANAGE_LOTS],
    )
    resp = await client.post(
        f"{BASE}/{created['id']}/cancel",
        json={"expected_edit_version": created["edit_version"]},
        headers=await auth_headers(manager),
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "canceled"


# ── GET /production-lots/bulk ───────────────────────────────────────────


async def test_read_lots_bulk_returns_full_lot_response(
    auth_client, made_item_and_project: tuple[int, int], owner: User, db: Session
) -> None:
    """Proves the bulk endpoint returns full LotResponse objects (unlike
    the summary-shaped GET /), by seeding a position directly through the
    repository (append_lot_position needs a real fabrication method, out
    of proportion to set up here) and checking its JSON carries `sequence`
    /`steps`/`supplier_name`, fields LotSummaryPositionResponse omits
    (see production_lot_schema.py's LotPositionResponse vs
    LotSummaryPositionResponse)."""
    made_item_id, project_id = made_item_and_project
    client = await auth_client(permissions=[Permission.WRITE_LOTS])
    lot_with_position = await _create_lot(client, made_item_id, project_id)
    bare_lot = await _create_lot(client, made_item_id, project_id)

    await SqlAlchemyProductionLotRepository(db).save_position(
        LotPosition(
            id=0,
            created=datetime.now(UTC),
            changed=None,
            changes=[],
            sequence=1,
            kind=LotPositionKind.UNASSIGNED,
            status=LotPositionStatus.PENDING,
            quantity=10.0,
            quantity_completed=0.0,
            note=None,
            creator_id=owner.id,
            lot_id=lot_with_position["id"],
        )
    )
    await db.commit()

    resp = await client.get(
        f"{BASE}/bulk", params={"ids": [lot_with_position["id"], bare_lot["id"]]}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert {item["id"] for item in body} == {lot_with_position["id"], bare_lot["id"]}

    positioned = next(item for item in body if item["id"] == lot_with_position["id"])
    assert len(positioned["positions"]) == 1
    position = positioned["positions"][0]
    assert position["sequence"] == 1
    assert position["steps"] == []
    assert position["supplier_name"] == ""


async def test_read_lots_bulk_omits_unknown_ids_without_404ing(
    auth_client, made_item_and_project: tuple[int, int]
) -> None:
    made_item_id, project_id = made_item_and_project
    client = await auth_client(permissions=[Permission.WRITE_LOTS])
    created = await _create_lot(client, made_item_id, project_id)

    resp = await client.get(f"{BASE}/bulk", params={"ids": [created["id"], 999_999]})

    assert resp.status_code == 200
    body = resp.json()
    assert [item["id"] for item in body] == [created["id"]]


async def test_read_lots_bulk_rejects_over_200_ids(auth_client) -> None:
    client = await auth_client(permissions=[])

    resp = await client.get(f"{BASE}/bulk", params={"ids": list(range(1, 202))})

    assert resp.status_code == 422


async def test_read_lots_bulk_requires_authentication(client) -> None:
    resp = await client.get(f"{BASE}/bulk", params={"ids": [1]})
    assert resp.status_code == 401


async def test_records_the_changing_user(
    auth_client, made_item_and_project: tuple[int, int]
) -> None:
    made_item_id, project_id = made_item_and_project
    writer = await auth_client(permissions=[Permission.WRITE_LOTS])
    editor = await auth_client(
        permissions=[Permission.WRITE_LOTS], username="lot-editor", email="lot-editor@example.com"
    )
    created = await _create_lot(writer, made_item_id, project_id)

    resp = await editor.patch(
        f"{BASE}/{created['id']}",
        json={"note": "Edited", "expected_edit_version": created["edit_version"]},
    )

    assert resp.status_code == 200, resp.text
    updated = resp.json()
    assert updated["creator_id"] == created["creator_id"]
    assert updated["changed_by_id"] not in (None, created["creator_id"])
    assert updated["changed_by"]["id"] == updated["changed_by_id"]
    reread = (await writer.get(f"{BASE}/{created['id']}")).json()
    assert reread["changed_by_id"] == updated["changed_by_id"]
    listed = (
        await writer.get(f"{BASE}/", params={"changed_by_id": updated["changed_by_id"]})
    ).json()
    assert [(lot["id"], lot["changed_by_id"]) for lot in listed["items"]] == [
        (created["id"], updated["changed_by_id"])
    ]
    assert listed["items"][0]["changed"] is not None
    listed = (await writer.get(f"{BASE}/", params={"changed_by_id": created["creator_id"]})).json()
    assert listed["items"] == []
    changed_day = updated["changed"][:10]
    listed = (
        await writer.get(
            f"{BASE}/", params={"changed_from": changed_day, "changed_to": changed_day}
        )
    ).json()
    assert [lot["id"] for lot in listed["items"]] == [created["id"]]
    listed = (await writer.get(f"{BASE}/", params={"changed_to": "2000-01-01"})).json()
    assert listed["items"] == []
