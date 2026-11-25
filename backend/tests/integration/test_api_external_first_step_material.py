"""
A lot whose routing sends its first position to a supplier needs no material
of ours: it starts awaiting its first step, with no source item demand and
nothing to approve. Turning the production setting off gives such a lot its
material need back, pending approval or with a demand at once. Runs through
the HTTP API on the test database, with the drift check at the end.
"""

from datetime import UTC
from datetime import datetime

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.value_objects.permission import Permission
from src.modules.workspace.adapters.outbound.persistence.repositories.project_repository import (
    SqlAlchemyProjectRepository,
)
from src.modules.workspace.domain.entities.project import Project
from tests.integration.test_api_lot_source_approval import _create_lot
from tests.integration.test_api_lot_source_approval import _demands_for_lot
from tests.integration.test_api_lot_source_approval import _get_lot
from tests.integration.test_api_lot_source_approval import _make_made_item
from tests.integration.test_api_lot_source_approval import _make_source_item
from tests.integration.test_api_lot_source_approval import _role_client

# Autouse: seeds the made-items and production settings CreateLot reads.
from tests.integration.test_api_lot_source_approval import _seed_settings  # noqa: F401
from tests.integration.test_api_lot_source_approval import _set_require_source_item_approval

SETTINGS_BASE = "/api/v1/web/admin/settings/production"
MADE_ITEMS_BASE = "/api/v1/web/made-items"

_PERMISSIONS = [
    Permission.WRITE_SETTINGS,
    Permission.READ_SETTINGS,
    Permission.WRITE_LOTS,
    Permission.MANAGE_LOTS,
    Permission.WRITE_MADE_ITEMS,
    Permission.WRITE_FABRICATION_METHODS,
]


async def _method(client: httpx.AsyncClient, name: str, *, external: bool) -> int:
    resp = await client.post(
        "/api/v1/web/fabrication-methods/",
        json={"name": {"enGB": name}, "required_external": external},
    )
    assert resp.status_code == 201, resp.text
    return int(resp.json()["id"])


async def _routed_made_item(
    db: AsyncSession, client: httpx.AsyncClient, owner_id: int, *, first_external: bool
) -> int:
    """A made item with a source item and two processes, the first with a
    method that is required external or not, the second made in house."""
    source_item_id = await _make_source_item(db, owner_id, suffix=str(first_external))
    made_item_id = await _make_made_item(
        db, owner_id, source_item_id=source_item_id, suffix=str(first_external)
    )
    first = await _method(client, f"Laser {first_external}", external=first_external)
    second = await _method(client, f"Bend {first_external}", external=False)
    for method_id in (first, second):
        resp = await client.post(
            f"{MADE_ITEMS_BASE}/{made_item_id}/processes",
            json={"fabrication_method_id": method_id},
        )
        assert resp.status_code == 201, resp.text
    return made_item_id


async def _set_first_step_rule(client: httpx.AsyncClient, enabled: bool) -> dict:
    resp = await client.put(SETTINGS_BASE, json={"external_first_step_needs_no_material": enabled})
    assert resp.status_code == 200, resp.text
    return dict(resp.json())


@pytest.fixture
async def owner(create_user) -> User:
    return await create_user(username="lot-owner", email="lot-owner@example.com")


@pytest.fixture
async def project_id(db: AsyncSession, owner: User) -> int:
    """Committed, so the API's own session can write while the test runs."""
    project = await SqlAlchemyProjectRepository(db).save(
        Project(id=0, created=datetime.now(UTC), creator_id=owner.id, project_number="P-EXT-1")
    )
    await db.commit()
    return project.id


@pytest.fixture
async def client(create_user) -> httpx.AsyncClient:
    client, _ = await _role_client(create_user, "planner", _PERMISSIONS)
    return client


class TestExternalFirstStepMaterial:
    async def test_the_setting_is_on_by_default(self, client: httpx.AsyncClient) -> None:
        resp = await client.get(SETTINGS_BASE)
        assert resp.status_code == 200, resp.text
        assert resp.json()["external_first_step_needs_no_material"] is True

    async def test_external_first_step_lot_awaits_it_without_a_demand(
        self, db: AsyncSession, client: httpx.AsyncClient, owner: User, project_id: int
    ) -> None:
        made_item_id = await _routed_made_item(db, client, owner.id, first_external=True)

        lot = await _create_lot(client, made_item_id, project_id)

        assert lot["source_approval_status"] == "awaiting_first_step"
        assert lot["input_demand_id"] is None
        assert (await _demands_for_lot(client, lot["id"]))["total"] == 0

    async def test_in_house_first_step_lot_demands_as_before(
        self, db: AsyncSession, client: httpx.AsyncClient, owner: User, project_id: int
    ) -> None:
        made_item_id = await _routed_made_item(db, client, owner.id, first_external=False)

        lot = await _create_lot(client, made_item_id, project_id)

        assert lot["source_approval_status"] == "not_required"
        assert lot["input_demand_id"] is not None

    async def test_turning_the_setting_off_demands_the_material(
        self, db: AsyncSession, client: httpx.AsyncClient, owner: User, project_id: int
    ) -> None:
        made_item_id = await _routed_made_item(db, client, owner.id, first_external=True)
        lot = await _create_lot(client, made_item_id, project_id)

        await _set_first_step_rule(client, False)

        restored = await _get_lot(client, lot["id"])
        assert restored["source_approval_status"] == "not_required"
        assert restored["input_demand_id"] is not None
        demands = (await _demands_for_lot(client, lot["id"]))["items"]
        assert [d["quantity"] for d in demands] == [5.0]

    async def test_turning_it_off_with_approval_on_puts_the_lot_into_approval(
        self, db: AsyncSession, client: httpx.AsyncClient, owner: User, project_id: int
    ) -> None:
        await _set_require_source_item_approval(client, True)
        made_item_id = await _routed_made_item(db, client, owner.id, first_external=True)
        lot = await _create_lot(client, made_item_id, project_id)
        assert lot["source_approval_status"] == "awaiting_first_step"

        await _set_first_step_rule(client, False)

        restored = await _get_lot(client, lot["id"])
        assert restored["source_approval_status"] == "pending"
        assert restored["input_demand_id"] is None

    async def test_turning_it_on_again_leaves_the_lots_alone(
        self, db: AsyncSession, client: httpx.AsyncClient, owner: User, project_id: int
    ) -> None:
        await _set_first_step_rule(client, False)
        made_item_id = await _routed_made_item(db, client, owner.id, first_external=True)
        lot = await _create_lot(client, made_item_id, project_id)
        assert lot["input_demand_id"] is not None

        await _set_first_step_rule(client, True)

        unchanged = await _get_lot(client, lot["id"])
        assert unchanged["source_approval_status"] == "not_required"
        assert unchanged["input_demand_id"] == lot["input_demand_id"]
