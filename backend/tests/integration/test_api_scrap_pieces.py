"""
HTTP-level round trip for POST /production-orders/{id}/scrap and POST
/production-lots/{id}/scrap.
Prerequisites (project, made item, lot, position, machine, order) are
seeded directly through the real repositories, the same pattern
test_api_production_order_time_tracking.py uses; only the routers under
test go through HTTP. The seeded lot is a rework lot (source_made_item_id
set) so StartProductionOrder's sequence-1 raw-material gating doesn't
apply, mirroring that same file's fixture trick.
"""

from datetime import UTC
from datetime import datetime

import httpx
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
from src.modules.platform.domain.value_objects.permission import Permission
from src.modules.workspace.adapters.outbound.persistence.repositories.project_repository import (
    SqlAlchemyProjectRepository,
)
from src.modules.workspace.domain.entities.project import Project
from tests.integration._edit_versions import lot_version
from tests.integration._edit_versions import production_order_version
from tests.integration._lot_facts import give_lot_facts
from tests.integration.conftest import auth_headers

ORDERS_BASE = "/api/v1/web/production-orders"
LOTS_BASE = "/api/v1/web/production-lots"


@pytest.fixture(autouse=True)
async def _seed_production_settings(db: Session) -> None:
    """ScrapProductionPieces tries a schedule recompute after commit;
    mirrors test_api_production_orders.py's own fixture."""
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


async def _make_item(db: Session, creator_id: int, part_number: str) -> MadeItem:
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
            article_name="Scrap test part",
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


async def _seed_lot_and_order(
    db: Session,
    creator_id: int,
    *,
    lot_number: str,
    quantity: float = 5.0,
    lot_status: LotStatus = LotStatus.PLANNED,
    order_status: ProductionOrderStatus = ProductionOrderStatus.QUEUED,
) -> tuple[ProductionLot, ProductionOrder]:
    project = await SqlAlchemyProjectRepository(db).save(
        Project(
            id=0,
            created=datetime.now(UTC),
            creator_id=creator_id,
            designated_user_id=creator_id,
            project_number=lot_number,
        )
    )
    made_item = await _make_item(db, creator_id, lot_number)
    lot_repo = SqlAlchemyProductionLotRepository(db)
    lot = await lot_repo.save(
        ProductionLot(
            id=0,
            created=datetime.now(UTC),
            changed=None,
            changes=[],
            lot_number=lot_number,
            quantity=quantity,
            status=lot_status,
            priority=UrgencyClass.NORMAL,
            note=None,
            creator_id=creator_id,
            made_item_id=made_item.id,
            project_id=project.id,
            input_demand_id=None,
            # Rework lot: exempt from the sequence-1 raw-material gating
            # StartProductionOrder otherwise applies (see module docstring).
            source_made_item_id=made_item.id,
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
            quantity=quantity,
            quantity_completed=0.0,
            note=None,
            creator_id=creator_id,
            lot_id=lot.id,
        )
    )
    machine = await SqlAlchemyProductionMachineRepository(db).save(
        ProductionMachine(
            id=0,
            created=datetime.now(UTC).date(),
            changed=None,
            changes=[],
            archived=False,
            internal_name=f"{lot_number}-MILL",
            vendor="Contoso",
            model="VF-2",
            fabrication_method_ids=[],
            max_part_dimension=None,
            note=None,
            creator_id=creator_id,
        )
    )
    await db.commit()
    order = await SqlAlchemyProductionOrderRepository(db).save(
        ProductionOrder(
            id=0,
            created=datetime.now(UTC),
            changed=None,
            changes=[],
            production_order_number=f"{lot_number}-PO-1",
            status=order_status,
            priority=UrgencyClass.NORMAL,
            pinned=False,
            queue_sequence=1,
            quantity=quantity,
            quantity_completed=0.0,
            estimated_duration_minutes=30,
            note=None,
            planned_start=datetime(2026, 3, 1, 8, 0, tzinfo=UTC),
            planned_end=datetime(2026, 3, 1, 12, 0, tzinfo=UTC),
            not_before=None,
            actual_start=(
                datetime(2026, 3, 1, 8, 0, tzinfo=UTC)
                if order_status == ProductionOrderStatus.IN_PROGRESS.value
                else None
            ),
            actual_end=None,
            creator_id=creator_id,
            machine_id=machine.id,
            lot_position_id=position.id,
        )
    )
    await give_lot_facts(db, lot.id)
    await db.commit()
    return lot, order


@pytest.fixture
async def owner(create_user) -> User:
    return await create_user(
        username="scrap-owner",
        email="scrap-owner@example.com",
        permissions=[Permission.WRITE_PRODUCTION_ORDERS],
    )


# A seeded order and lot as read; the requests that use it are refused
# before their versions are compared, by a user who may not read the rows.
_seeded_versions = {"expected_edit_version": 0, "expected_lot_edit_version": 0}


async def _versions(
    client: httpx.AsyncClient, order_id: int, lot_id: int, headers: dict[str, str]
) -> dict[str, int]:
    """The order's and its lot's edit versions as read now."""
    return {
        "expected_edit_version": await production_order_version(client, order_id, headers),
        "expected_lot_edit_version": await lot_version(client, lot_id, headers),
    }


class TestScrapProductionOrderEndpoint:
    async def test_scrap_full_quantity_creates_replacement_lot_over_http(
        self, db: Session, client, owner: User
    ) -> None:
        _lot, order = await _seed_lot_and_order(db, owner.id, lot_number="LOT-SC-1", quantity=3.0)
        headers = await auth_headers(owner)

        started = await client.post(f"{ORDERS_BASE}/{order.id}/start", json={}, headers=headers)
        assert started.status_code == 200

        response = await client.post(
            f"{ORDERS_BASE}/{order.id}/scrap",
            json={
                "quantity": 3.0,
                "reason": "tool_breakage",
                "create_replacement": True,
                **await _versions(client, order.id, order.lot_id, headers),
            },
            headers=headers,
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["lot"]["status"] == "scrapped"
        assert body["lot"]["quantity_scrapped"] == 3.0
        assert len(body["created_lots"]) == 1
        assert body["created_lots"][0]["disposition"] == "replacement"
        assert body["lot"]["replacement_lot_ids"] == [body["created_lots"][0]["id"]]

    async def test_a_retried_scrap_replays_the_lot_and_its_replacement(
        self, db: Session, client, owner: User
    ) -> None:
        _lot, order = await _seed_lot_and_order(db, owner.id, lot_number="LOT-SC-R", quantity=3.0)
        headers = {**await auth_headers(owner), "Idempotency-Key": "scrap-1"}
        await client.post(f"{ORDERS_BASE}/{order.id}/start", json={}, headers=headers)
        body = {
            "quantity": 3.0,
            "reason": "tool_breakage",
            "create_replacement": True,
            **await _versions(client, order.id, order.lot_id, headers),
        }

        first = await client.post(f"{ORDERS_BASE}/{order.id}/scrap", json=body, headers=headers)
        retry = await client.post(f"{ORDERS_BASE}/{order.id}/scrap", json=body, headers=headers)

        assert first.status_code == 200, first.text
        assert retry.status_code == 200, retry.text
        assert retry.json()["created_lots"] == first.json()["created_lots"]
        assert retry.json()["lot"]["quantity_scrapped"] == 3.0

    async def test_a_scrap_against_an_older_edit_version_is_refused(
        self, db: Session, client, owner: User
    ) -> None:
        _lot, order = await _seed_lot_and_order(db, owner.id, lot_number="LOT-SC-V", quantity=3.0)
        headers = await auth_headers(owner)
        await client.post(f"{ORDERS_BASE}/{order.id}/start", json={}, headers=headers)
        body = {"quantity": 1.0, "reason": "tool_breakage", "create_replacement": False}

        first = await client.post(
            f"{ORDERS_BASE}/{order.id}/scrap",
            json={**body, "expected_edit_version": 0, "expected_lot_edit_version": 0},
            headers=headers,
        )
        stale = await client.post(
            f"{ORDERS_BASE}/{order.id}/scrap",
            json={**body, "expected_edit_version": 0, "expected_lot_edit_version": 0},
            headers=headers,
        )

        assert first.status_code == 200, first.text
        assert stale.status_code == 409, stale.text
        assert first.json()["lot"]["edit_version"] == 1

    async def test_scrap_over_capacity_returns_422(self, db: Session, client, owner: User) -> None:
        _lot, order = await _seed_lot_and_order(db, owner.id, lot_number="LOT-SC-2", quantity=3.0)
        headers = await auth_headers(owner)
        await client.post(f"{ORDERS_BASE}/{order.id}/start", json={}, headers=headers)

        response = await client.post(
            f"{ORDERS_BASE}/{order.id}/scrap",
            json={
                "quantity": 10.0,
                "reason": "tool_breakage",
                **await _versions(client, order.id, order.lot_id, headers),
            },
            headers=headers,
        )
        assert response.status_code == 422, response.text
        assert response.json()["code"] == "ScrapQuantityExceedsAvailableError"

    async def test_scrap_on_terminal_lot_returns_409(
        self, db: Session, client, owner: User
    ) -> None:
        # order.status is seeded IN_PROGRESS directly (not via /start) so
        # the lot's own terminal status, not the order's, is what
        # /scrap rejects on.
        _lot, order = await _seed_lot_and_order(
            db,
            owner.id,
            lot_number="LOT-SC-3",
            quantity=3.0,
            lot_status=LotStatus.CANCELED,
            order_status=ProductionOrderStatus.IN_PROGRESS,
        )
        headers = await auth_headers(owner)

        response = await client.post(
            f"{ORDERS_BASE}/{order.id}/scrap",
            json={"quantity": 1.0, "reason": "tool_breakage", **_seeded_versions},
            headers=headers,
        )
        assert response.status_code == 409, response.text
        assert response.json()["code"] == "LotNotScrappableError"

    async def test_scrap_requires_production_order_write_permission(
        self, db: Session, client, create_user
    ) -> None:
        no_perms = await create_user(
            username="scrap-no-perms", email="scrap-no-perms@example.com", permissions=[]
        )
        _lot, order = await _seed_lot_and_order(
            db, no_perms.id, lot_number="LOT-SC-4", quantity=3.0
        )
        headers = await auth_headers(no_perms)

        response = await client.post(
            f"{ORDERS_BASE}/{order.id}/scrap",
            json={"quantity": 1.0, "reason": "tool_breakage", **_seeded_versions},
            headers=headers,
        )
        assert response.status_code == 403, response.text


class TestScrapLotEndpoint:
    async def test_scrap_via_lot_endpoint_resolves_single_open_order(
        self, db: Session, client, owner: User
    ) -> None:
        lot, order = await _seed_lot_and_order(db, owner.id, lot_number="LOT-SC-5", quantity=4.0)
        headers = await auth_headers(owner)
        await client.post(f"{ORDERS_BASE}/{order.id}/start", json={}, headers=headers)

        response = await client.post(
            f"{LOTS_BASE}/{lot.id}/scrap",
            json={
                "position_id": order.lot_position_id,
                "quantity": 1.0,
                "reason": "operator_error",
                "create_replacement": False,
                "expected_edit_version": await lot_version(client, lot.id, headers),
            },
            headers=headers,
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["lot"]["quantity_scrapped"] == 1.0
        assert body["lot"]["quantity"] == 3.0
        assert body["created_lots"] == []

    async def test_scrap_via_lot_endpoint_refuses_an_order_of_another_lot(
        self, db: Session, client, owner: User
    ) -> None:
        lot, order = await _seed_lot_and_order(db, owner.id, lot_number="LOT-SC-8")
        _, foreign = await _seed_lot_and_order(db, owner.id, lot_number="LOT-SC-9")
        headers = await auth_headers(owner)

        response = await client.post(
            f"{LOTS_BASE}/{lot.id}/scrap",
            json={
                "position_id": order.lot_position_id,
                "production_order_id": foreign.id,
                "quantity": 1.0,
                "reason": "operator_error",
                "create_replacement": False,
                "expected_edit_version": await lot_version(client, lot.id, headers),
            },
            headers=headers,
        )

        assert response.status_code == 404, response.text
        assert response.json()["code"] == "ProductionOrderNotFoundError"

    # The seeded order is stored canceled without its intent.
    @pytest.mark.usefixtures("allow_lifecycle_drift")
    async def test_scrap_via_lot_endpoint_explains_a_position_without_open_work(
        self, db: Session, client, owner: User
    ) -> None:
        lot, order = await _seed_lot_and_order(
            db, owner.id, lot_number="LOT-SC-10", order_status=ProductionOrderStatus.CANCELED
        )
        headers = await auth_headers(owner)

        response = await client.post(
            f"{LOTS_BASE}/{lot.id}/scrap",
            json={
                "position_id": order.lot_position_id,
                "quantity": 1.0,
                "reason": "operator_error",
                "create_replacement": False,
                "expected_edit_version": await lot_version(client, lot.id, headers),
            },
            headers=headers,
        )

        assert response.status_code == 409, response.text
        assert response.json()["code"] == "LotNotScrappableError"
        assert "no open production order" in response.json()["detail"]
