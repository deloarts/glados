"""
HTTP-level coverage of the Source Item Approval feature: the new
POST /{lot_id}/source/approve and /source/reject routes on
production-lots, the require_source_item_approval production setting
(including its off->on/on->off lot backfill), and the
source_approval_status list filter. Prerequisites (project, made item,
source item, bought item) are seeded through the real repositories, the
routes under test are exercised through the real FastAPI app + SQLite-
backed DB, mirroring tests/integration/test_api_production_lots.py.
"""

from datetime import UTC
from datetime import datetime

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.bootstrap.adapters.outbound.persistence.repositories.admin_settings_repository import (
    SqlAlchemyAdminSettingsRepository,
)
from src.modules.catalogue.adapters.outbound.persistence.repositories.bought_item_repository.item import (
    SqlAlchemyBoughtItemRepository,
)
from src.modules.catalogue.adapters.outbound.persistence.repositories.made_item_repository.item import (
    SqlAlchemyMadeItemRepository,
)
from src.modules.catalogue.adapters.outbound.persistence.repositories.source_item_repository import (
    SqlAlchemySourceItemRepository,
)
from src.modules.catalogue.adapters.outbound.persistence.repositories.source_item_type_repository import (
    SqlAlchemySourceItemTypeRepository,
)
from src.modules.catalogue.domain.entities.admin_settings.made_items import AdminMadeItemSettings
from src.modules.catalogue.domain.entities.bought_item import BoughtItem
from src.modules.catalogue.domain.entities.made_item import MadeItem
from src.modules.catalogue.domain.entities.source_item import SourceItem
from src.modules.catalogue.domain.entities.source_item_type import SourceItemType
from src.modules.catalogue.domain.policies.item_field_ownership import default_policy
from src.modules.catalogue.domain.value_objects.bought_item_status import BoughtItemCatalogueStatus
from src.modules.catalogue.domain.value_objects.data_source import DataSource
from src.modules.catalogue.domain.value_objects.made_item_status import MadeItemCatalogueStatus
from src.modules.catalogue.domain.value_objects.source_item_status import SourceItemCatalogueStatus
from src.modules.fulfillment.domain.entities.admin_settings.production import (
    AdminProductionSettings,
)
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.value_objects.localized_text import LocalizedText
from src.modules.platform.domain.value_objects.permission import Permission
from src.modules.workspace.adapters.outbound.persistence.repositories.project_repository import (
    SqlAlchemyProjectRepository,
)
from src.modules.workspace.domain.entities.project import Project
from src.modules.workspace.domain.value_objects.project_status import ProjectStatus
from tests.integration.conftest import _new_client
from tests.integration.conftest import auth_headers

LOTS_BASE = "/api/v1/web/production-lots"
SETTINGS_BASE = "/api/v1/web/admin/settings/production"
DEMANDS_BASE = "/api/v1/web/source-item-demands"


# ── Fixtures ─────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
async def _seed_settings(db: AsyncSession) -> None:
    """CreateLot reads both the made-items (lot numbering) and production
    (require_source_item_approval among others) admin-settings domains;
    neither is seeded by conftest.py's `_seed_admin_settings`. Mirrors
    test_api_production_lots.py. require_source_item_approval is left at
    its dataclass default (False); tests that need it on flip it through
    the PUT endpoint under test, not by seeding it pre-flipped."""
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
async def project_id(db: AsyncSession, owner: User) -> int:
    project = await SqlAlchemyProjectRepository(db).save(
        Project(id=0, created=datetime.now(UTC), creator_id=owner.id, project_number="P-SRC-1")
    )
    return project.id


async def _make_source_item(db: AsyncSession, creator_id: int, *, suffix: str = "1") -> int:
    source_item_type = await SqlAlchemySourceItemTypeRepository(db).save(
        SourceItemType(
            id=0,
            created=datetime.now(UTC),
            changed=datetime.now(UTC),
            changes=[],
            archived=False,
            name=LocalizedText({"enGB": f"Round bar {suffix}"}),
            label_color="#000000",
            label_font_color="#ffffff",
            description=LocalizedText(),
            creator_id=creator_id,
        )
    )
    source_item = await SqlAlchemySourceItemRepository(db).save(
        SourceItem(
            id=0,
            created=datetime.now(UTC),
            changed=datetime.now(UTC),
            changes=[],
            archived=False,
            type_id=source_item_type.id,
            dimension="40mm",
            material="1.0037",
            mass=None,
            note=None,
            order_code_1=None,
            order_code_2=None,
            status=SourceItemCatalogueStatus.ACTIVE,
            creator_id=creator_id,
            approver_id=None,
            manufacturer_id=None,
            successor_item_id=None,
        )
    )
    await db.commit()
    return source_item.id


async def _make_bought_item(db: AsyncSession, creator_id: int, *, suffix: str = "1") -> int:
    bought_item = await SqlAlchemyBoughtItemRepository(db).save(
        BoughtItem(
            id=0,
            created=datetime.now(UTC),
            changed=datetime.now(UTC),
            changes=[],
            archived=False,
            article_name=f"Widget {suffix}",
            order_code_1=f"OC-{suffix}",
            order_code_2=None,
            gtin=None,
            ean=None,
            tariff_number=None,
            status=BoughtItemCatalogueStatus.ACTIVE,
            data_source=DataSource.WEB,
            part_number=None,
            mass=None,
            note=None,
            weblink=None,
            files=[],
            creator_id=creator_id,
            approver_id=None,
            manufacturer_id=1,
            article_group_ids=[],
            successor_item_id=None,
        )
    )
    return bought_item.id


async def _make_made_item(
    db: AsyncSession,
    creator_id: int,
    *,
    source_item_id: int | None = None,
    bought_item_id: int | None = None,
    suffix: str = "1",
) -> int:
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
            article_name=f"Approval part {suffix}",
            status=MadeItemCatalogueStatus.ACTIVE,
            data_source=DataSource.WEB,
            part_number=None,
            material=None,
            mass=None,
            base_size=None,
            note=None,
            weblink=None,
            files=[],
            creator_id=creator_id,
            approver_id=None,
            bought_item_id=bought_item_id,
            source_item_id=source_item_id,
            article_group_ids=[],
            successor_item_id=None,
            changed_by_id=None,
        )
    )
    await db.commit()
    return made_item.id


@pytest.fixture
async def source_made_item_id(db: AsyncSession, owner: User) -> int:
    """A made item whose material source is a SourceItem, the kind the
    approval gate applies to."""
    source_item_id = await _make_source_item(db, owner.id)
    return await _make_made_item(db, owner.id, source_item_id=source_item_id, suffix="source")


@pytest.fixture
async def bought_made_item_id(db: AsyncSession, owner: User) -> int:
    """A made item whose material source is a BoughtItem, never gated."""
    bought_item_id = await _make_bought_item(db, owner.id)
    return await _make_made_item(db, owner.id, bought_item_id=bought_item_id, suffix="bought")


async def _create_lot(client, made_item_id: int, project_id: int, *, quantity: float = 5.0) -> dict:
    resp = await client.post(
        f"{LOTS_BASE}/",
        json={"made_item_id": made_item_id, "project_id": project_id, "quantity": quantity},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _get_lot(client, lot_id: int) -> dict:
    resp = await client.get(f"{LOTS_BASE}/{lot_id}")
    assert resp.status_code == 200, resp.text
    return resp.json()


async def _set_require_source_item_approval(client, enabled: bool) -> dict:
    resp = await client.put(SETTINGS_BASE, json={"require_source_item_approval": enabled})
    assert resp.status_code == 200, resp.text
    return resp.json()


async def _role_client(
    create_user, name: str, permissions: list[str]
) -> tuple[httpx.AsyncClient, int]:
    """Like the `auth_client` fixture (tests/integration/conftest.py), but
    also hands back the created user's id: several assertions here need to
    know who acted (source_approved_by_id / source_rejected_by_id), which
    a plain `auth_client`-bound client does not expose. Each call needs
    its own username/email, since create_user defaults both, so a test using
    several differently-permissioned clients (admin + writer + approver)
    would otherwise collide on user_table's unique email."""
    user = await create_user(username=name, email=f"{name}@example.com", permissions=permissions)
    client = _new_client()
    client.headers.update(await auth_headers(user))
    return client, user.id


async def _demands_for_lot(client, lot_id: int) -> dict:
    resp = await client.get(DEMANDS_BASE + "/", params={"lot_id": lot_id})
    assert resp.status_code == 200, resp.text
    return resp.json()


# ── Creation: pending vs not_required ───────────────────────────────


class TestLotCreationUnderApproval:
    async def test_source_item_lot_is_pending_with_no_demand_when_setting_is_on(
        self, create_user, project_id: int, source_made_item_id: int
    ) -> None:
        admin, _admin_id = await _role_client(create_user, "admin", [Permission.WRITE_SETTINGS])
        await _set_require_source_item_approval(admin, True)

        writer, _writer_id = await _role_client(create_user, "writer", [Permission.WRITE_LOTS])
        created = await _create_lot(writer, source_made_item_id, project_id)

        lot = await _get_lot(writer, created["id"])
        assert lot["source_approval_status"] == "pending"
        assert lot["input_demand_id"] is None

        page = await _demands_for_lot(writer, created["id"])
        assert page["total"] == 0
        assert page["items"] == []

    async def test_bought_item_lot_still_gets_its_demand_immediately_when_setting_is_on(
        self, create_user, project_id: int, bought_made_item_id: int
    ) -> None:
        admin, _admin_id = await _role_client(create_user, "admin", [Permission.WRITE_SETTINGS])
        await _set_require_source_item_approval(admin, True)

        writer, _writer_id = await _role_client(create_user, "writer", [Permission.WRITE_LOTS])
        created = await _create_lot(writer, bought_made_item_id, project_id)

        lot = await _get_lot(writer, created["id"])
        assert lot["source_approval_status"] == "not_required"
        assert lot["input_demand_id"] is not None

        page = await _demands_for_lot(writer, created["id"])
        assert page["total"] == 1


# ── Approve ──────────────────────────────────────────────────────────


class TestApproveLotSourceApi:
    async def test_approve_releases_the_lot_and_creates_its_demand(
        self, create_user, project_id: int, source_made_item_id: int
    ) -> None:
        admin, _admin_id = await _role_client(create_user, "admin", [Permission.WRITE_SETTINGS])
        await _set_require_source_item_approval(admin, True)

        writer, _writer_id = await _role_client(create_user, "writer", [Permission.WRITE_LOTS])
        created = await _create_lot(writer, source_made_item_id, project_id)

        approver, approver_id = await _role_client(
            create_user, "approver", [Permission.MANAGE_LOTS]
        )
        resp = await approver.post(
            f"{LOTS_BASE}/{created['id']}/source/approve",
            json={"expected_edit_version": created["edit_version"]},
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()

        assert body["source_approval_status"] == "approved"
        assert body["source_approved_by_id"] == approver_id
        assert body["source_approved_date"] is not None
        assert body["input_demand_id"] is not None
        assert body["source_rejected_by_id"] is None
        assert body["source_rejected_date"] is None
        assert body["source_rejection_reason"] is None

        page = await _demands_for_lot(writer, created["id"])
        assert page["total"] == 1

    async def test_approve_requires_manage_lots(
        self, create_user, project_id: int, source_made_item_id: int
    ) -> None:
        admin, _admin_id = await _role_client(create_user, "admin", [Permission.WRITE_SETTINGS])
        await _set_require_source_item_approval(admin, True)

        writer, _writer_id = await _role_client(create_user, "writer", [Permission.WRITE_LOTS])
        created = await _create_lot(writer, source_made_item_id, project_id)

        resp = await writer.post(
            f"{LOTS_BASE}/{created['id']}/source/approve",
            json={"expected_edit_version": created["edit_version"]},
        )
        assert resp.status_code == 403, resp.text

    async def test_approve_a_non_pending_lot_is_a_conflict(
        self, create_user, project_id: int, source_made_item_id: int
    ) -> None:
        admin, _admin_id = await _role_client(create_user, "admin", [Permission.WRITE_SETTINGS])
        await _set_require_source_item_approval(admin, True)

        writer, _writer_id = await _role_client(create_user, "writer", [Permission.WRITE_LOTS])
        created = await _create_lot(writer, source_made_item_id, project_id)

        approver, _approver_id = await _role_client(
            create_user, "approver", [Permission.MANAGE_LOTS]
        )
        first = await approver.post(
            f"{LOTS_BASE}/{created['id']}/source/approve",
            json={"expected_edit_version": created["edit_version"]},
        )
        assert first.status_code == 200, first.text

        second = await approver.post(
            f"{LOTS_BASE}/{created['id']}/source/approve",
            json={"expected_edit_version": first.json()["edit_version"]},
        )
        assert second.status_code == 409, second.text


class TestSourceDecisionGuardsApi:
    async def test_an_approval_from_a_view_before_a_switch_is_refused(
        self, db: AsyncSession, create_user, owner: User, project_id: int, source_made_item_id: int
    ) -> None:
        admin, _admin_id = await _role_client(create_user, "admin", [Permission.WRITE_SETTINGS])
        await _set_require_source_item_approval(admin, True)
        writer, _writer_id = await _role_client(create_user, "writer", [Permission.WRITE_LOTS])
        created = await _create_lot(writer, source_made_item_id, project_id)
        other_source_id = await _make_source_item(db, owner.id, suffix="2")

        switched = await writer.put(
            f"{LOTS_BASE}/{created['id']}/material-source",
            json={
                "source_item_id": other_source_id,
                "expected_edit_version": created["edit_version"],
            },
        )
        assert switched.status_code == 200, switched.text
        assert switched.json()["source_approval_status"] == "pending"
        assert switched.json()["edit_version"] > created["edit_version"]

        approver, _approver_id = await _role_client(
            create_user, "approver", [Permission.MANAGE_LOTS]
        )
        stale = await approver.post(
            f"{LOTS_BASE}/{created['id']}/source/approve",
            json={"expected_edit_version": created["edit_version"]},
        )
        assert stale.status_code == 409, stale.text
        lot = await _get_lot(writer, created["id"])
        assert lot["source_approval_status"] == "pending"
        assert lot["input_demand_id"] is None

    async def test_an_approval_on_a_project_on_hold_is_refused(
        self, db: AsyncSession, create_user, project_id: int, source_made_item_id: int
    ) -> None:
        admin, _admin_id = await _role_client(create_user, "admin", [Permission.WRITE_SETTINGS])
        await _set_require_source_item_approval(admin, True)
        writer, _writer_id = await _role_client(create_user, "writer", [Permission.WRITE_LOTS])
        created = await _create_lot(writer, source_made_item_id, project_id)

        projects = SqlAlchemyProjectRepository(db)
        project = await projects.get_by_id(project_id)
        assert project is not None
        project.status = ProjectStatus.ON_HOLD
        await projects.save(project)
        await db.commit()

        approver, _approver_id = await _role_client(
            create_user, "approver", [Permission.MANAGE_LOTS]
        )
        resp = await approver.post(
            f"{LOTS_BASE}/{created['id']}/source/approve",
            json={"expected_edit_version": created["edit_version"]},
        )
        assert resp.status_code == 409, resp.text
        assert "on hold" in resp.text
        assert (await _demands_for_lot(writer, created["id"]))["total"] == 0

    async def test_the_source_actions_follow_the_lot_and_its_approval(
        self, create_user, project_id: int, source_made_item_id: int
    ) -> None:
        admin, _admin_id = await _role_client(create_user, "admin", [Permission.WRITE_SETTINGS])
        await _set_require_source_item_approval(admin, True)
        manager, _manager_id = await _role_client(
            create_user, "manager", [Permission.WRITE_LOTS, Permission.MANAGE_LOTS]
        )
        created = await _create_lot(manager, source_made_item_id, project_id)
        source_actions = {"approve_source", "reject_source", "switch_source"}

        pending = await _get_lot(manager, created["id"])
        assert source_actions <= set(pending["actions"])

        canceled = await manager.post(
            f"{LOTS_BASE}/{created['id']}/cancel",
            json={"expected_edit_version": pending["edit_version"]},
        )
        assert canceled.status_code == 200, canceled.text
        assert not source_actions & set(canceled.json()["actions"])

        refused = await manager.post(
            f"{LOTS_BASE}/{created['id']}/source/approve",
            json={"expected_edit_version": canceled.json()["edit_version"]},
        )
        assert refused.status_code == 409, refused.text


# ── Reject ───────────────────────────────────────────────────────────


class TestRejectLotSourceApi:
    async def test_blank_reason_is_rejected_with_422(
        self, create_user, project_id: int, source_made_item_id: int
    ) -> None:
        admin, _admin_id = await _role_client(create_user, "admin", [Permission.WRITE_SETTINGS])
        await _set_require_source_item_approval(admin, True)

        writer, _writer_id = await _role_client(create_user, "writer", [Permission.WRITE_LOTS])
        created = await _create_lot(writer, source_made_item_id, project_id)

        approver, _approver_id = await _role_client(
            create_user, "approver", [Permission.MANAGE_LOTS]
        )
        resp = await approver.post(
            f"{LOTS_BASE}/{created['id']}/source/reject",
            json={"reason": "   ", "expected_edit_version": created["edit_version"]},
        )
        assert resp.status_code == 422, resp.text

    async def test_reject_then_approve_round_trip(
        self, create_user, project_id: int, source_made_item_id: int
    ) -> None:
        admin, _admin_id = await _role_client(create_user, "admin", [Permission.WRITE_SETTINGS])
        await _set_require_source_item_approval(admin, True)

        writer, _writer_id = await _role_client(create_user, "writer", [Permission.WRITE_LOTS])
        created = await _create_lot(writer, source_made_item_id, project_id)

        approver, approver_id = await _role_client(
            create_user, "approver", [Permission.MANAGE_LOTS]
        )
        reject_resp = await approver.post(
            f"{LOTS_BASE}/{created['id']}/source/reject",
            json={
                "reason": "  Wrong dimension.  ",
                "expected_edit_version": created["edit_version"],
            },
        )
        assert reject_resp.status_code == 200, reject_resp.text
        rejected = reject_resp.json()
        assert rejected["source_approval_status"] == "rejected"
        assert rejected["source_rejected_by_id"] == approver_id
        # RejectLotSourceRequest's field_validator strips before length is
        # meaningful, so the stored reason must not carry the padding.
        assert rejected["source_rejection_reason"] == "Wrong dimension."
        assert rejected["source_approved_by_id"] is None
        assert rejected["source_approved_date"] is None
        assert rejected["input_demand_id"] is None

        approve_resp = await approver.post(
            f"{LOTS_BASE}/{created['id']}/source/approve",
            json={"expected_edit_version": rejected["edit_version"]},
        )
        assert approve_resp.status_code == 200, approve_resp.text
        approved = approve_resp.json()
        assert approved["source_approval_status"] == "approved"
        assert approved["source_rejected_by_id"] is None
        assert approved["source_rejected_date"] is None
        assert approved["source_rejection_reason"] is None
        assert approved["input_demand_id"] is not None


# ── Needs Approval list filter ──────────────────────────────────────


class TestSourceApprovalStatusFilter:
    async def test_filter_lists_only_pending_lots(
        self, create_user, project_id: int, source_made_item_id: int, bought_made_item_id: int
    ) -> None:
        admin, _admin_id = await _role_client(create_user, "admin", [Permission.WRITE_SETTINGS])
        await _set_require_source_item_approval(admin, True)

        writer, _writer_id = await _role_client(create_user, "writer", [Permission.WRITE_LOTS])
        pending = await _create_lot(writer, source_made_item_id, project_id)
        # Bought-item source is never gated: it stays not_required, and must not
        # show up in the pending-only filter.
        not_required = await _create_lot(writer, bought_made_item_id, project_id)

        resp = await writer.get(f"{LOTS_BASE}/", params={"source_approval_status": "pending"})
        assert resp.status_code == 200, resp.text
        body = resp.json()
        returned_ids = {row["id"] for row in body["items"]}

        assert pending["id"] in returned_ids
        assert not_required["id"] not in returned_ids

        pending_row = next(row for row in body["items"] if row["id"] == pending["id"])
        assert pending_row["source_approval_status"] == "pending"
        assert "source_rejection_reason" in pending_row


# ── Setting toggle backfill ──────────────────────────────────────────


class TestSourceApprovalSettingToggleBackfill:
    async def test_toggle_flips_a_demandless_lot_and_leaves_an_approved_lot_alone(
        self, create_user, project_id: int, source_made_item_id: int
    ) -> None:
        writer, _writer_id = await _role_client(create_user, "writer", [Permission.WRITE_LOTS])
        admin, _admin_id = await _role_client(create_user, "admin", [Permission.WRITE_SETTINGS])
        approver, _approver_id = await _role_client(
            create_user, "approver", [Permission.MANAGE_LOTS]
        )

        # Created while the setting is OFF: not_required, demand created
        # immediately, same as today.
        backfill_candidate = await _create_lot(writer, source_made_item_id, project_id)
        lot = await _get_lot(writer, backfill_candidate["id"])
        assert lot["source_approval_status"] == "not_required"
        demand_id = lot["input_demand_id"]
        assert demand_id is not None

        # Clear input_demand_id so the lot matches the backfill predicate
        # (source_item_id set, input_demand_id NULL, non-terminal,
        # not_required); see reset_source_approval_for_setting_change.
        cancel_resp = await writer.post(
            f"{DEMANDS_BASE}/{demand_id}/cancel", params={"cancel_lot": "false"}
        )
        assert cancel_resp.status_code == 200, cancel_resp.text
        lot = await _get_lot(writer, backfill_candidate["id"])
        assert lot["input_demand_id"] is None
        assert lot["source_approval_status"] == "not_required"

        # Turn the setting ON: the demandless not_required lot backfills to
        # pending.
        await _set_require_source_item_approval(admin, True)
        lot = await _get_lot(writer, backfill_candidate["id"])
        assert lot["source_approval_status"] == "pending"

        # A second lot, created (and approved) while the setting is ON, to
        # prove a config flip never rewrites a recorded decision.
        approved_candidate = await _create_lot(writer, source_made_item_id, project_id)
        approve_resp = await approver.post(
            f"{LOTS_BASE}/{approved_candidate['id']}/source/approve",
            json={"expected_edit_version": approved_candidate["edit_version"]},
        )
        assert approve_resp.status_code == 200, approve_resp.text
        assert approve_resp.json()["source_approval_status"] == "approved"

        # Turn the setting back OFF: the pending lot reverses to
        # not_required; the approved lot is untouched.
        await _set_require_source_item_approval(admin, False)
        lot = await _get_lot(writer, backfill_candidate["id"])
        assert lot["source_approval_status"] == "not_required"
        approved_lot = await _get_lot(writer, approved_candidate["id"])
        assert approved_lot["source_approval_status"] == "approved"

        # And ON again: the demandless lot flips back to pending, the
        # approved lot still untouched.
        await _set_require_source_item_approval(admin, True)
        lot = await _get_lot(writer, backfill_candidate["id"])
        assert lot["source_approval_status"] == "pending"
        approved_lot = await _get_lot(writer, approved_candidate["id"])
        assert approved_lot["source_approval_status"] == "approved"
