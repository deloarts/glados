"""
HTTP-level coverage of ApproveLotSource's optional write-back of an
approved lot's source item onto its made item's MadeItem.source_item_id,
gated by the assign_approved_material_to_item / overwrite_item_material_
on_approval production settings (see approve_lot_source.py and
material_source_rules.resolve_made_item_source_assignment). Exercised
through POST /production-lots/{id}/source/approve, mirroring
tests/integration/test_api_lot_source_approval.py.

Fixtures/helpers are imported (pure functions) or copied (fixtures:
_seed_settings is autouse, kept as a local copy the same way test_api_
production_lots.py already keeps its own independent copy rather than
relying on cross-module autouse fixture pickup) from that file rather than
duplicated from scratch.
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
from src.modules.catalogue.domain.policies.item_field_ownership import default_policy
from src.modules.fulfillment.domain.entities.admin_settings.production import (
    AdminProductionSettings,
)
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.value_objects.permission import Permission
from src.modules.workspace.adapters.outbound.persistence.repositories.project_repository import (
    SqlAlchemyProjectRepository,
)
from src.modules.workspace.domain.entities.project import Project
from tests.integration.test_api_lot_source_approval import _create_lot
from tests.integration.test_api_lot_source_approval import _get_lot
from tests.integration.test_api_lot_source_approval import _make_bought_item
from tests.integration.test_api_lot_source_approval import _make_made_item
from tests.integration.test_api_lot_source_approval import _make_source_item
from tests.integration.test_api_lot_source_approval import _role_client
from tests.integration.test_api_lot_source_approval import _set_require_source_item_approval

LOTS_BASE = "/api/v1/web/production-lots"
SETTINGS_BASE = "/api/v1/web/admin/settings/production"
MADE_ITEMS_BASE = "/api/v1/web/made-items"


# ── Fixtures ─────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
async def _seed_settings(db: Session) -> None:
    """Copy of test_api_lot_source_approval.py's own fixture (see that
    file's docstring for why): CreateLot reads both made-items and
    production admin-settings domains, neither seeded by conftest.py's
    `_seed_admin_settings`)."""
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
async def owner(create_user) -> User:
    return await create_user(username="lot-owner", email="lot-owner@example.com")


@pytest.fixture
async def project_id(db: Session, owner: User) -> int:
    project = await SqlAlchemyProjectRepository(db).save(
        Project(id=0, created=datetime.now(UTC), creator_id=owner.id, project_number="P-MAT-1")
    )
    return project.id


# ── Helpers ──────────────────────────────────────────────────────────


async def _set_material_assignment_settings(
    client, *, assign: bool | None = None, overwrite: bool | None = None
) -> dict:
    body: dict = {}
    if assign is not None:
        body["assign_approved_material_to_item"] = assign
    if overwrite is not None:
        body["overwrite_item_material_on_approval"] = overwrite
    resp = await client.put(SETTINGS_BASE, json=body)
    assert resp.status_code == 200, resp.text
    return resp.json()


async def _get_made_item(client, item_id: int) -> dict:
    resp = await client.get(f"{MADE_ITEMS_BASE}/{item_id}")
    assert resp.status_code == 200, resp.text
    return resp.json()


async def _set_made_item_source(
    db: Session, item_id: int, *, source_item_id: int | None, bought_item_id: int | None
) -> None:
    """Simulates a made item whose source has drifted (cleared, switched to
    a bought item, or pointed at a different source item) since the lot
    that references it was created. A lot's own source_item_id is
    captured once at CreateLot time and does not stay in sync afterwards
    (see create_lot.py). Writes directly through the repository rather
    than PUT /made-items/{id}: the made-item revision system rejects
    an in-place change to source_item_id/bought_item_id on a WEB item
    through that endpoint (a policy field requires a new revision), which
    would fight this test's premise of simulating drift outside the web
    path."""
    repo = SqlAlchemyMadeItemRepository(db)
    item = await repo.get_by_id(item_id)
    assert item is not None
    item.bought_item_id = bought_item_id
    item.source_item_id = source_item_id
    await repo.save(item)
    await db.commit()


async def _make_clients(create_user):
    """The four roles this file's scenarios need: an admin to flip
    settings, a writer to create lots, a made-item writer to simulate the
    made item's source drifting after lot creation, and an approver
    carrying ONLY manage:lots (no write:made_items), since the
    write-back runs on manage:lots alone."""
    admin, _ = await _role_client(create_user, "admin", [Permission.WRITE_SETTINGS])
    writer, _ = await _role_client(create_user, "writer", [Permission.WRITE_LOTS])
    item_writer, _ = await _role_client(create_user, "item-writer", [Permission.WRITE_MADE_ITEMS])
    approver, approver_id = await _role_client(create_user, "approver", [Permission.MANAGE_LOTS])
    return admin, writer, item_writer, approver, approver_id


# ── Tests ────────────────────────────────────────────────────────────


class TestApproveLotSourceMaterialAssignmentApi:
    async def test_assign_on_empty_slot_assigns_the_source_item(
        self, create_user, db: Session, owner: User, project_id: int
    ) -> None:
        admin, writer, item_writer, approver, _ = await _make_clients(create_user)
        await _set_require_source_item_approval(admin, True)
        await _set_material_assignment_settings(admin, assign=True, overwrite=False)

        source_item_id = await _make_source_item(db, owner.id, suffix="a")
        made_item_id = await _make_made_item(
            db, owner.id, source_item_id=source_item_id, suffix="a"
        )
        created = await _create_lot(writer, made_item_id, project_id)

        # Simulate the made item's source having been cleared after the lot
        # was created. The lot itself still carries source_item_id from
        # creation time.
        await _set_made_item_source(db, made_item_id, source_item_id=None, bought_item_id=None)
        assert (await _get_made_item(item_writer, made_item_id))["source_item_id"] is None

        resp = await approver.post(
            f"{LOTS_BASE}/{created['id']}/source/approve",
            json={"expected_edit_version": created["edit_version"]},
        )
        assert resp.status_code == 200, resp.text

        made_item = await _get_made_item(writer, made_item_id)
        assert made_item["source_item_id"] == source_item_id

    async def test_assign_off_leaves_the_made_item_unchanged(
        self, create_user, db: Session, owner: User, project_id: int
    ) -> None:
        admin, writer, _item_writer, approver, _ = await _make_clients(create_user)
        await _set_require_source_item_approval(admin, True)
        await _set_material_assignment_settings(admin, assign=False, overwrite=True)

        source_item_id = await _make_source_item(db, owner.id, suffix="b")
        made_item_id = await _make_made_item(
            db, owner.id, source_item_id=source_item_id, suffix="b"
        )
        created = await _create_lot(writer, made_item_id, project_id)

        await _set_made_item_source(db, made_item_id, source_item_id=None, bought_item_id=None)

        resp = await approver.post(
            f"{LOTS_BASE}/{created['id']}/source/approve",
            json={"expected_edit_version": created["edit_version"]},
        )
        assert resp.status_code == 200, resp.text

        made_item = await _get_made_item(writer, made_item_id)
        assert made_item["source_item_id"] is None

    async def test_bought_item_present_is_never_touched_even_with_overwrite_on(
        self, create_user, db: Session, owner: User, project_id: int
    ) -> None:
        admin, writer, _item_writer, approver, _ = await _make_clients(create_user)
        await _set_require_source_item_approval(admin, True)
        await _set_material_assignment_settings(admin, assign=True, overwrite=True)

        source_item_id = await _make_source_item(db, owner.id, suffix="c")
        made_item_id = await _make_made_item(
            db, owner.id, source_item_id=source_item_id, suffix="c"
        )
        created = await _create_lot(writer, made_item_id, project_id)

        bought_item_id = await _make_bought_item(db, owner.id, suffix="c")
        await _set_made_item_source(
            db, made_item_id, source_item_id=None, bought_item_id=bought_item_id
        )

        resp = await approver.post(
            f"{LOTS_BASE}/{created['id']}/source/approve",
            json={"expected_edit_version": created["edit_version"]},
        )
        assert resp.status_code == 200, resp.text

        made_item = await _get_made_item(writer, made_item_id)
        assert made_item["bought_item_id"] == bought_item_id
        assert made_item["source_item_id"] is None

    async def test_different_source_item_overwrite_off_leaves_it_unchanged(
        self, create_user, db: Session, owner: User, project_id: int
    ) -> None:
        admin, writer, _item_writer, approver, _ = await _make_clients(create_user)
        await _set_require_source_item_approval(admin, True)
        await _set_material_assignment_settings(admin, assign=True, overwrite=False)

        lot_source_item_id = await _make_source_item(db, owner.id, suffix="d1")
        other_source_item_id = await _make_source_item(db, owner.id, suffix="d2")
        made_item_id = await _make_made_item(
            db, owner.id, source_item_id=lot_source_item_id, suffix="d"
        )
        created = await _create_lot(writer, made_item_id, project_id)

        await _set_made_item_source(
            db, made_item_id, source_item_id=other_source_item_id, bought_item_id=None
        )

        resp = await approver.post(
            f"{LOTS_BASE}/{created['id']}/source/approve",
            json={"expected_edit_version": created["edit_version"]},
        )
        assert resp.status_code == 200, resp.text

        made_item = await _get_made_item(writer, made_item_id)
        assert made_item["source_item_id"] == other_source_item_id

    async def test_different_source_item_overwrite_on_replaces_it(
        self, create_user, db: Session, owner: User, project_id: int
    ) -> None:
        admin, writer, _item_writer, approver, _ = await _make_clients(create_user)
        await _set_require_source_item_approval(admin, True)
        await _set_material_assignment_settings(admin, assign=True, overwrite=True)

        lot_source_item_id = await _make_source_item(db, owner.id, suffix="e1")
        other_source_item_id = await _make_source_item(db, owner.id, suffix="e2")
        made_item_id = await _make_made_item(
            db, owner.id, source_item_id=lot_source_item_id, suffix="e"
        )
        created = await _create_lot(writer, made_item_id, project_id)

        await _set_made_item_source(
            db, made_item_id, source_item_id=other_source_item_id, bought_item_id=None
        )

        resp = await approver.post(
            f"{LOTS_BASE}/{created['id']}/source/approve",
            json={"expected_edit_version": created["edit_version"]},
        )
        assert resp.status_code == 200, resp.text

        made_item = await _get_made_item(writer, made_item_id)
        assert made_item["source_item_id"] == lot_source_item_id

    async def test_approver_with_only_manage_lots_still_triggers_the_write(
        self, create_user, db: Session, owner: User, project_id: int
    ) -> None:
        """The write-back runs on manage:lots alone, no
        write:made_items check. _make_clients' `approver` carries only
        manage:lots."""
        admin, writer, _item_writer, approver, _ = await _make_clients(create_user)
        await _set_require_source_item_approval(admin, True)
        await _set_material_assignment_settings(admin, assign=True, overwrite=False)

        source_item_id = await _make_source_item(db, owner.id, suffix="f")
        made_item_id = await _make_made_item(
            db, owner.id, source_item_id=source_item_id, suffix="f"
        )
        created = await _create_lot(writer, made_item_id, project_id)

        await _set_made_item_source(db, made_item_id, source_item_id=None, bought_item_id=None)

        resp = await approver.post(
            f"{LOTS_BASE}/{created['id']}/source/approve",
            json={"expected_edit_version": created["edit_version"]},
        )
        assert resp.status_code == 200, resp.text

        made_item = await _get_made_item(writer, made_item_id)
        assert made_item["source_item_id"] == source_item_id

    async def test_approval_still_succeeds_even_when_write_back_is_skipped(
        self, create_user, db: Session, owner: User, project_id: int
    ) -> None:
        """Approval, the demand, and input_demand_id always
        go through regardless of the write-back outcome."""
        admin, writer, _item_writer, approver, approver_id = await _make_clients(create_user)
        await _set_require_source_item_approval(admin, True)
        await _set_material_assignment_settings(admin, assign=True, overwrite=False)

        source_item_id = await _make_source_item(db, owner.id, suffix="g")
        made_item_id = await _make_made_item(
            db, owner.id, source_item_id=source_item_id, suffix="g"
        )
        created = await _create_lot(writer, made_item_id, project_id)

        bought_item_id = await _make_bought_item(db, owner.id, suffix="g")
        await _set_made_item_source(
            db, made_item_id, source_item_id=None, bought_item_id=bought_item_id
        )

        resp = await approver.post(
            f"{LOTS_BASE}/{created['id']}/source/approve",
            json={"expected_edit_version": created["edit_version"]},
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["source_approval_status"] == "approved"
        assert body["source_approved_by_id"] == approver_id
        assert body["input_demand_id"] is not None

        lot = await _get_lot(writer, created["id"])
        assert lot["input_demand_id"] is not None
