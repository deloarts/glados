"""
HTTP-level coverage of /api/v1/web/production-orders: state machine
and permissions against a real database. Prerequisites (project, made
item, lot, position, production order) are seeded directly through the
real repositories, the same pattern test_production_order_repository.py
and test_api_lot_position_in_use.py already use, only the router under
test goes through HTTP.

`start` is deliberately not exercised here: a sequence-1 INTERNAL
position with no raw-material demand always resolves 0.0 available input
(see StartProductionOrder._assert_upstream_available), so making it
succeed needs either an alteration lot or a multi-position chain with a
completed predecessor, out of proportion for this router's net. `cancel`
covers the state-machine + terminal-state + permission shape instead,
with fewer preconditions.
"""

from datetime import UTC
from datetime import date
from datetime import datetime

import pytest
from sqlalchemy.orm import Session

from src.bootstrap.adapters.outbound.persistence.repositories.admin_settings_repository import (
    SqlAlchemyAdminSettingsRepository,
)
from src.modules.catalogue.adapters.outbound.persistence.repositories.made_item_repository.item import (
    SqlAlchemyMadeItemRepository,
)
from src.modules.catalogue.domain.entities.made_item import MadeItem
from src.modules.catalogue.domain.value_objects.data_source import DataSource
from src.modules.catalogue.domain.value_objects.made_item_status import MadeItemCatalogueStatus
from src.modules.fulfillment.adapters.outbound.persistence.repositories.production_lot_repository.lot import (
    SqlAlchemyProductionLotRepository,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.production_machine_repository import (
    SqlAlchemyProductionMachineRepository,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.production_order_repository import (
    SqlAlchemyProductionOrderRepository,
)
from src.modules.fulfillment.domain.entities.admin_settings.production import (
    AdminProductionSettings,
)
from src.modules.fulfillment.domain.entities.lot_position import LotPosition
from src.modules.fulfillment.domain.entities.production_lot import ProductionLot
from src.modules.fulfillment.domain.entities.production_machine import ProductionMachine
from src.modules.fulfillment.domain.entities.production_order import ProductionOrder
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionKind
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionStatus
from src.modules.fulfillment.domain.value_objects.lot_status import LotStatus
from src.modules.fulfillment.domain.value_objects.production_status import ProductionOrderStatus
from src.modules.fulfillment.domain.value_objects.production_status import UrgencyClass
from src.modules.platform.domain.entities.user import User
from src.modules.workspace.adapters.outbound.persistence.repositories.project_repository import (
    SqlAlchemyProjectRepository,
)
from src.modules.workspace.domain.entities.project import Project
from tests.integration._lot_facts import give_lot_facts
from tests.integration._production_order_facts import give_production_order_facts
from tests.integration.conftest import auth_headers

BASE = "/api/v1/web/production-orders"


@pytest.fixture(autouse=True)
async def _seed_production_settings(db: Session) -> None:
    """UpdateProductionOrder recomputes the machine schedule, which reads
    the production numbering/calendar domain; `_seed_admin_settings`
    (conftest.py) does not cover it. Mirrors InitDatabase's own seed
    values."""
    await SqlAlchemyAdminSettingsRepository(db).save_production(
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


async def _make_item(db: Session, creator_id: int) -> MadeItem:
    seeded = await SqlAlchemyMadeItemRepository(db).save(
        MadeItem(
            id=0,
            created=datetime.now(UTC),
            changed=datetime.now(UTC),
            changes=[],
            archived=False,
            revision="0",
            revision_date=None,
            revision_note=None,
            article_name="PO surface part",
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
            bought_item_id=None,
            source_item_id=None,
            article_group_ids=[],
            successor_item_id=None,
            changed_by_id=None,
        )
    )
    await db.commit()
    return seeded


async def _seed_order(
    db: Session, creator_id: int, *, status: ProductionOrderStatus = ProductionOrderStatus.QUEUED
):
    project = await SqlAlchemyProjectRepository(db).save(
        Project(id=0, created=datetime.now(UTC), creator_id=creator_id, project_number="P-PO-1")
    )
    made_item = await _make_item(db, creator_id)
    lot_repo = SqlAlchemyProductionLotRepository(db)
    lot = await lot_repo.save(
        ProductionLot(
            id=0,
            created=datetime.now(UTC),
            changed=None,
            changes=[],
            lot_number="LN-PO-1",
            quantity=10.0,
            status=LotStatus.PLANNED,
            priority=UrgencyClass.NORMAL,
            note=None,
            creator_id=creator_id,
            made_item_id=made_item.id,
            project_id=project.id,
            input_demand_id=None,
        )
    )
    position = await lot_repo.save_position(
        LotPosition(
            id=0,
            created=datetime.now(UTC),
            changed=None,
            changes=[],
            sequence=1,
            kind=LotPositionKind.INTERNAL,
            status=LotPositionStatus.ORDERED_OR_QUEUED,
            quantity=10.0,
            quantity_completed=0.0,
            note=None,
            creator_id=creator_id,
            lot_id=lot.id,
        )
    )
    machine = await SqlAlchemyProductionMachineRepository(db).save(
        ProductionMachine(
            id=0,
            created=date.today(),
            changed=None,
            changes=[],
            archived=False,
            internal_name="PO-MILL-1",
            vendor="Contoso",
            model="VF-2",
            fabrication_method_ids=[],
            max_part_dimension=None,
            note=None,
            creator_id=creator_id,
        )
    )
    await db.commit()
    saved = await SqlAlchemyProductionOrderRepository(db).save(
        ProductionOrder(
            id=0,
            created=datetime.now(UTC),
            changed=None,
            changes=[],
            production_order_number="PO-SURFACE-1",
            status=status,
            priority=UrgencyClass.NORMAL,
            pinned=False,
            queue_sequence=1,
            quantity=10.0,
            quantity_completed=0.0,
            estimated_duration_minutes=30,
            note=None,
            planned_start=None,
            planned_end=None,
            not_before=None,
            actual_start=None,
            actual_end=None,
            creator_id=creator_id,
            machine_id=machine.id,
            lot_position_id=position.id,
        )
    )
    await give_production_order_facts(db, saved.id)
    # The lot follows the seeded order, whatever its status.
    await give_lot_facts(db, lot.id, exact=False)
    await db.commit()
    return saved


@pytest.fixture
async def owner(create_user) -> User:
    return await create_user(username="po-owner", email="po-owner@example.com")


async def test_list_production_orders(db: Session, auth_client, owner: User) -> None:
    await _seed_order(db, owner.id)
    client = await auth_client(username="reader", email="po-reader@example.com", permissions=[])
    resp = await client.get(f"{BASE}/")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] >= 1
    assert any(o["production_order_number"] == "PO-SURFACE-1" for o in body["items"])


async def test_read_production_order(db: Session, auth_client, owner: User) -> None:
    order = await _seed_order(db, owner.id)
    client = await auth_client(username="reader2", email="po-reader2@example.com", permissions=[])
    resp = await client.get(f"{BASE}/{order.id}")
    assert resp.status_code == 200
    assert resp.json()["status"] == ProductionOrderStatus.QUEUED.value


async def test_read_missing_production_order_404(auth_client) -> None:
    client = await auth_client(permissions=[])
    resp = await client.get(f"{BASE}/999999")
    assert resp.status_code == 404


async def test_update_production_order_requires_write_permission(
    db: Session, owner: User, client
) -> None:
    order = await _seed_order(db, owner.id)
    resp = await client.patch(
        f"{BASE}/{order.id}",
        json={"note": "hi", "expected_edit_version": order.edit_version},
        headers=await auth_headers(owner),
    )
    # `owner` was created with no permissions at all (create_user default).
    assert resp.status_code == 403


@pytest.mark.smoke
async def test_update_production_order(db: Session, auth_client, owner: User) -> None:
    order = await _seed_order(db, owner.id)
    client = await auth_client(
        username="updater", email="po-updater@example.com", permissions=["write:production_orders"]
    )
    resp = await client.patch(
        f"{BASE}/{order.id}",
        json={"note": "Recut on Monday.", "expected_edit_version": order.edit_version},
    )
    assert resp.status_code == 200
    assert resp.json()["note"] == "Recut on Monday."


async def test_updated_production_order_is_persisted(db: Session, auth_client, owner: User) -> None:
    order = await _seed_order(db, owner.id)
    client = await auth_client(
        username="updater", email="po-updater@example.com", permissions=["write:production_orders"]
    )
    resp = await client.patch(
        f"{BASE}/{order.id}",
        json={"note": "Recut on Monday.", "expected_edit_version": order.edit_version},
    )
    assert resp.status_code == 200

    reread = await client.get(f"{BASE}/{order.id}")
    assert reread.json()["note"] == "Recut on Monday."


async def test_split_production_order_rejects_single_quantity(
    db: Session, auth_client, owner: User
) -> None:
    order = await _seed_order(db, owner.id)
    client = await auth_client(
        username="splitter",
        email="po-splitter@example.com",
        permissions=["write:production_orders"],
    )
    resp = await client.post(f"{BASE}/{order.id}/split", json={"quantities": [10.0]})
    assert resp.status_code == 422


async def test_cancel_production_order_by_creator_succeeds(
    db: Session, client, owner: User
) -> None:
    """A creator may cancel their own order without manage:production_orders."""
    order = await _seed_order(db, owner.id)
    resp = await client.post(
        f"{BASE}/{order.id}/cancel",
        json={"expected_edit_version": order.edit_version},
        headers=await auth_headers(owner),
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == ProductionOrderStatus.CANCELED.value


async def test_cancel_production_order_by_stranger_is_forbidden(
    db: Session, client, owner: User, create_user
) -> None:
    order = await _seed_order(db, owner.id)
    stranger = await create_user(username="po-stranger", email="po-stranger@example.com")
    resp = await client.post(
        f"{BASE}/{order.id}/cancel",
        json={"expected_edit_version": order.edit_version},
        headers=await auth_headers(stranger),
    )
    assert resp.status_code == 403


async def test_cancel_already_canceled_production_order_is_terminal(
    db: Session, client, owner: User
) -> None:
    order = await _seed_order(db, owner.id, status=ProductionOrderStatus.CANCELED)
    resp = await client.post(
        f"{BASE}/{order.id}/cancel",
        json={"expected_edit_version": order.edit_version},
        headers=await auth_headers(owner),
    )
    assert resp.status_code == 422
