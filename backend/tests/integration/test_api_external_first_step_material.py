"""
A lot whose routing sends its first position to a supplier needs no material
of ours: it starts awaiting its first step, with no source item demand and
nothing to approve. Turning the production setting off gives such a lot its
material need back, pending approval or with a demand at once. When the
first position changes hands later, the lifecycle reconciler's material
follow-up moves the status and settles, resizes or creates the demand. Runs
through the HTTP API on the test database, with the drift check at the end.
"""

from datetime import UTC
from datetime import datetime

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.fulfillment.adapters.outbound.persistence.repositories.order_repository.order import (
    SqlAlchemyOrderRepository,
)
from src.modules.fulfillment.domain.entities.order import Order
from src.modules.fulfillment.domain.value_objects.order_status import OrderStatus
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.value_objects.permission import Permission
from src.modules.workspace.adapters.outbound.persistence.repositories.project_repository import (
    SqlAlchemyProjectRepository,
)
from src.modules.workspace.domain.entities.project import Project
from tests.integration.repository_reads._graph import Graph
from tests.integration.repository_reads._graph import make
from tests.integration.test_api_lot_source_approval import LOTS_BASE
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
    Permission.WRITE_ORDERS,
    Permission.MANAGE_ORDERS,
    Permission.WRITE_PRODUCTION_ORDERS,
]


async def _method(client: httpx.AsyncClient, name: str, *, external: bool) -> int:
    resp = await client.post(
        "/api/v1/web/fabrication-methods/",
        json={"name": {"enGB": name}, "required_external": external, "requires_machine": False},
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


# ── The first position changes hands ────────────────────────────────


@pytest.fixture
async def supplier_order_id(db: AsyncSession) -> int:
    """A draft order of a supplier, which takes the lines a position is
    assigned to."""
    graph = await Graph.seed(db)
    supplier = await graph.supplier()
    order = await SqlAlchemyOrderRepository(db).save(
        make(
            Order,
            order_number="O-EXT-1",
            status=OrderStatus.DRAFT,
            creator_id=graph.uid,
            supplier_id=supplier.id,
        )
    )
    await db.commit()
    return order.id


def _first_position_url(lot: dict) -> str:
    position = min(lot["positions"], key=lambda p: p["sequence"])
    return f"{LOTS_BASE}/{lot['id']}/positions/{position['id']}"


async def _to_supplier(
    client: httpx.AsyncClient, lot: dict, order_id: int, quantity: float | None = None
) -> dict:
    body: dict = {"order_id": order_id, "unit": "pcs"}
    if quantity is not None:
        body["quantity"] = quantity
    resp = await client.post(f"{_first_position_url(lot)}/assign", json=body)
    assert resp.status_code == 200, resp.text
    return dict(resp.json())


async def _in_house(client: httpx.AsyncClient, lot: dict, quantity: float) -> dict:
    resp = await client.post(
        f"{_first_position_url(lot)}/assign-internal", json={"orders": [{"quantity": quantity}]}
    )
    assert resp.status_code == 200, resp.text
    return dict(resp.json())


async def _demands(client: httpx.AsyncClient, lot_id: int) -> list[tuple[str, float]]:
    items = (await _demands_for_lot(client, lot_id))["items"]
    return sorted((d["status"], d["quantity"]) for d in items)


class TestFirstPositionChangesHands:
    async def test_a_supplier_taking_it_over_settles_the_demand(
        self,
        db: AsyncSession,
        client: httpx.AsyncClient,
        owner: User,
        project_id: int,
        supplier_order_id: int,
    ) -> None:
        made_item_id = await _routed_made_item(db, client, owner.id, first_external=False)
        lot = await _create_lot(client, made_item_id, project_id)

        assigned = await _to_supplier(client, await _get_lot(client, lot["id"]), supplier_order_id)

        assert assigned["kind"] == "external"
        after = await _get_lot(client, lot["id"])
        assert after["source_approval_status"] == "supplier_sourced"
        assert after["input_demand_id"] is None
        assert await _demands(client, lot["id"]) == [("canceled", 5.0)]

    async def test_its_supplier_line_going_away_demands_the_material_again(
        self,
        db: AsyncSession,
        client: httpx.AsyncClient,
        owner: User,
        project_id: int,
        supplier_order_id: int,
    ) -> None:
        made_item_id = await _routed_made_item(db, client, owner.id, first_external=False)
        lot = await _get_lot(client, (await _create_lot(client, made_item_id, project_id))["id"])
        await _to_supplier(client, lot, supplier_order_id)

        resp = await client.delete(f"{_first_position_url(lot)}/assign")

        assert resp.status_code == 204, resp.text
        after = await _get_lot(client, lot["id"])
        assert after["source_approval_status"] == "not_required"
        assert after["input_demand_id"] is not None
        assert await _demands(client, lot["id"]) == [("canceled", 5.0), ("open", 5.0)]

    async def test_an_awaited_first_step_made_in_house_demands_the_material(
        self, db: AsyncSession, client: httpx.AsyncClient, owner: User, project_id: int
    ) -> None:
        made_item_id = await _routed_made_item(db, client, owner.id, first_external=True)
        lot = await _get_lot(client, (await _create_lot(client, made_item_id, project_id))["id"])

        await _in_house(client, lot, 5.0)

        after = await _get_lot(client, lot["id"])
        assert after["source_approval_status"] == "not_required"
        assert await _demands(client, lot["id"]) == [("open", 5.0)]

    async def test_with_approval_on_it_waits_for_the_approval_instead(
        self, db: AsyncSession, client: httpx.AsyncClient, owner: User, project_id: int
    ) -> None:
        await _set_require_source_item_approval(client, True)
        made_item_id = await _routed_made_item(db, client, owner.id, first_external=True)
        lot = await _get_lot(client, (await _create_lot(client, made_item_id, project_id))["id"])

        await _in_house(client, lot, 5.0)

        after = await _get_lot(client, lot["id"])
        assert after["source_approval_status"] == "pending"
        assert after["input_demand_id"] is None
        assert await _demands(client, lot["id"]) == []

    async def test_an_awaited_first_step_given_to_a_supplier_needs_no_material(
        self,
        db: AsyncSession,
        client: httpx.AsyncClient,
        owner: User,
        project_id: int,
        supplier_order_id: int,
    ) -> None:
        made_item_id = await _routed_made_item(db, client, owner.id, first_external=True)
        lot = await _get_lot(client, (await _create_lot(client, made_item_id, project_id))["id"])

        await _to_supplier(client, lot, supplier_order_id)

        after = await _get_lot(client, lot["id"])
        assert after["source_approval_status"] == "supplier_sourced"
        assert await _demands(client, lot["id"]) == []

    async def test_a_shared_first_position_demands_the_in_house_share(
        self,
        db: AsyncSession,
        client: httpx.AsyncClient,
        owner: User,
        project_id: int,
        supplier_order_id: int,
    ) -> None:
        made_item_id = await _routed_made_item(db, client, owner.id, first_external=False)
        lot = await _get_lot(client, (await _create_lot(client, made_item_id, project_id))["id"])
        await _in_house(client, lot, 3.0)

        assigned = await _to_supplier(client, lot, supplier_order_id, quantity=2.0)

        assert assigned["kind"] == "mixed"
        after = await _get_lot(client, lot["id"])
        assert after["source_approval_status"] == "not_required"
        assert await _demands(client, lot["id"]) == [("open", 3.0)]

    async def test_with_the_setting_off_the_demand_stays(
        self,
        db: AsyncSession,
        client: httpx.AsyncClient,
        owner: User,
        project_id: int,
        supplier_order_id: int,
    ) -> None:
        await _set_first_step_rule(client, False)
        made_item_id = await _routed_made_item(db, client, owner.id, first_external=False)
        lot = await _get_lot(client, (await _create_lot(client, made_item_id, project_id))["id"])

        await _to_supplier(client, lot, supplier_order_id)

        after = await _get_lot(client, lot["id"])
        assert after["source_approval_status"] == "not_required"
        assert after["input_demand_id"] == lot["input_demand_id"]
        assert await _demands(client, lot["id"]) == [("open", 5.0)]
