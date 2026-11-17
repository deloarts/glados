"""
HTTP-level round trip for GET /production-kpi/scrap-by-reason and GET
/production-kpi/rejected-per-supplier. Prerequisites (project, made
item, lot, position, machine, order, supplier, order item) are seeded
directly through the real repositories and then driven through the real
scrap and delivery endpoints, so the completions and delivery records
under test go through the same disposition machinery production traffic
does; only the two KPI endpoints under test are read directly. Every
number in the assertions is derived by hand from the seeded/booked rows.
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
from src.modules.catalogue.adapters.outbound.persistence.repositories.supplier_repository import (
    SqlAlchemySupplierRepository,
)
from src.modules.catalogue.domain.entities.made_item import MadeItem
from src.modules.catalogue.domain.entities.supplier import Supplier
from src.modules.catalogue.domain.value_objects.data_source import DataSource
from src.modules.catalogue.domain.value_objects.made_item_status import MadeItemCatalogueStatus
from src.modules.catalogue.domain.value_objects.supplier_level import SupplierLevel
from src.modules.fulfillment.adapters.outbound.persistence.repositories.order_repository.order import (
    SqlAlchemyOrderRepository,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.order_repository.order_item import (
    SqlAlchemyOrderItemRepository,
)
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
from src.modules.fulfillment.domain.entities.order import Order
from src.modules.fulfillment.domain.entities.order_item import OrderItem
from src.modules.fulfillment.domain.entities.production_lot import ProductionLot
from src.modules.fulfillment.domain.entities.production_machine import ProductionMachine
from src.modules.fulfillment.domain.entities.production_order import ProductionOrder
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionKind
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionStatus
from src.modules.fulfillment.domain.value_objects.lot_status import LotStatus
from src.modules.fulfillment.domain.value_objects.order_status import OrderItemStatus
from src.modules.fulfillment.domain.value_objects.order_status import OrderLineType
from src.modules.fulfillment.domain.value_objects.order_status import OrderStatus
from src.modules.fulfillment.domain.value_objects.production_status import ProductionOrderStatus
from src.modules.fulfillment.domain.value_objects.production_status import UrgencyClass
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.value_objects.permission import Permission
from src.modules.workspace.adapters.outbound.persistence.repositories.project_repository import (
    SqlAlchemyProjectRepository,
)
from src.modules.workspace.domain.entities.project import Project
from tests.integration._tenant_day import tenant_today
from tests.integration.conftest import auth_headers

KPI_BASE = "/api/v1/web/production-kpi"
ORDERS_BASE = "/api/v1/web/production-orders"
DELIVER_URL = "/api/v1/web/bought-items-allocations/order-item"


def _period(day: date) -> dict[str, str]:
    """A KPI period of one day, built when the request is made, so a run
    that crosses midnight asks for the day its rows were booked on. Every
    KPI period is a span of the tenant's days."""
    return {"date_from": day.isoformat(), "date_to": day.isoformat()}


@pytest.fixture(autouse=True)
async def _seed_production_settings(db: Session) -> None:
    """ScrapProductionPieces tries a schedule recompute after commit;
    mirrors test_api_scrap_pieces.py's own fixture."""
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


@pytest.fixture
async def viewer(create_user) -> User:
    return await create_user(username="scrap-kpi-viewer", email="scrap-kpi-viewer@example.com")


async def _made_item(db: Session, creator_id: int, article_name: str) -> MadeItem:
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
            article_name=article_name,
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
    db: Session, creator_id: int, *, lot_number: str, quantity: float
) -> ProductionOrder:
    project = await SqlAlchemyProjectRepository(db).save(
        Project(id=0, created=datetime.now(UTC), creator_id=creator_id, project_number=lot_number)
    )
    made_item = await _made_item(db, creator_id, lot_number)
    lot_repo = SqlAlchemyProductionLotRepository(db)
    lot = await lot_repo.save(
        ProductionLot(
            id=0,
            created=datetime.now(UTC),
            changed=None,
            changes=[],
            lot_number=lot_number,
            quantity=quantity,
            status=LotStatus.PLANNED,
            priority=UrgencyClass.NORMAL,
            note=None,
            creator_id=creator_id,
            made_item_id=made_item.id,
            project_id=project.id,
            input_demand_id=None,
            # Rework lot: exempt from the sequence-1 raw-material gating
            # StartProductionOrder otherwise applies, mirrors
            # test_api_scrap_pieces.py's own fixture trick.
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
    saved = await SqlAlchemyProductionOrderRepository(db).save(
        ProductionOrder(
            id=0,
            created=datetime.now(UTC),
            changed=None,
            changes=[],
            production_order_number=f"{lot_number}-PO-1",
            status=ProductionOrderStatus.QUEUED,
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
            actual_start=None,
            actual_end=None,
            creator_id=creator_id,
            machine_id=machine.id,
            lot_position_id=position.id,
        )
    )
    await db.commit()
    return saved


async def _supplier(db: Session, creator_id: int, name: str) -> Supplier:
    saved = await SqlAlchemySupplierRepository(db).save(
        Supplier(
            id=0,
            created=datetime.now(UTC),
            changed=datetime.now(UTC),
            changes=[],
            archived=False,
            name=name,
            legal_name=None,
            vat_id=None,
            level=SupplierLevel.B,
            capability_ids=[],
            article_group_ids=[],
            street=None,
            city=None,
            country=None,
            postal_code=None,
            email=None,
            phone=None,
            weblink=None,
            order_email=None,
            order_language=None,
            order_template=None,
            request_email=None,
            request_language=None,
            request_template=None,
            creator_id=creator_id,
        )
    )
    await db.commit()
    return saved


async def _seed_virtual_order_item(
    db: Session, creator_id: int, supplier_id: int, *, order_number: str, quantity: float
) -> int:
    """One order with one VIRTUAL line under the given supplier, returns
    the order item id. VIRTUAL needs no bought/source/lot-position setup
    (see OrderItem.line_type's docstring), which keeps the "lost" branch
    a pure demand re-allocation with no lot side effect to seed for."""
    order = await SqlAlchemyOrderRepository(db).save(
        Order(
            id=0,
            order_number=order_number,
            created=datetime.now(UTC),
            changed=None,
            changes=[],
            status=OrderStatus.ORDERED,
            note=None,
            ordered_date=datetime.now(UTC),
            expected_delivery_date=None,
            delivery_date=None,
            storage_place=None,
            creator_id=creator_id,
            supplier_id=supplier_id,
        )
    )
    item = await SqlAlchemyOrderItemRepository(db).save(
        OrderItem(
            id=0,
            created=datetime.now(UTC),
            changed=None,
            changes=[],
            status=OrderItemStatus.ORDERED,
            quantity=quantity,
            quantity_delivered=0.0,
            unit="pcs",
            items_per_unit=1.0,
            price=None,
            note=None,
            ordered_date=datetime.now(UTC),
            expected_delivery_date=date(2026, 10, 1),
            delivery_date=None,
            storage_place=None,
            expected_pickup_date=None,
            ready_for_pickup_date=None,
            position=1,
            creator_id=creator_id,
            orderer_id=None,
            receiver_id=None,
            bought_item_id=None,
            order_id=order.id,
            supplier_id=supplier_id,
            project_id=(
                await SqlAlchemyProjectRepository(db).save(
                    Project(
                        id=0,
                        created=datetime.now(UTC),
                        creator_id=creator_id,
                        project_number=f"P-{order_number}",
                    )
                )
            ).id,
            line_type=OrderLineType.VIRTUAL,
            lot_position_id=None,
            source_item_id=None,
            virtual_name="Freight",
        )
    )
    await db.commit()
    return item.id


@pytest.fixture
async def scrap_owner(create_user) -> User:
    return await create_user(
        username="scrap-kpi-owner",
        email="scrap-kpi-owner@example.com",
        permissions=[Permission.WRITE_PRODUCTION_ORDERS],
    )


@pytest.fixture
async def receiver(create_user) -> User:
    return await create_user(
        username="scrap-kpi-receiver",
        email="scrap-kpi-receiver@example.com",
        permissions=[Permission.RECEIVE_DELIVERIES],
    )


# The seeded orders and lots as read: nobody has edited them yet.
_SEEDED_VERSIONS = {"expected_edit_version": 0, "expected_lot_edit_version": 0}


class TestScrapByReasonEndpoint:
    async def test_pools_scrap_completions_by_reason_with_hand_derived_shares(
        self, db: Session, client, scrap_owner: User, viewer: User
    ) -> None:
        # Lot A: order for 3 pieces, 2 scrapped as tool_breakage.
        order_a = await _seed_lot_and_order(
            db, scrap_owner.id, lot_number="LOT-SKPI-1", quantity=3.0
        )
        # Lot B: order for 1 piece, all scrapped as material_defect.
        order_b = await _seed_lot_and_order(
            db, scrap_owner.id, lot_number="LOT-SKPI-2", quantity=1.0
        )

        owner_headers = await auth_headers(scrap_owner)
        await client.post(f"{ORDERS_BASE}/{order_a.id}/start", json={}, headers=owner_headers)
        await client.post(f"{ORDERS_BASE}/{order_b.id}/start", json={}, headers=owner_headers)

        scrap_a = await client.post(
            f"{ORDERS_BASE}/{order_a.id}/scrap",
            json={
                "quantity": 2.0,
                "reason": "tool_breakage",
                "create_replacement": False,
                **_SEEDED_VERSIONS,
            },
            headers=owner_headers,
        )
        assert scrap_a.status_code == 200, scrap_a.text
        scrap_b = await client.post(
            f"{ORDERS_BASE}/{order_b.id}/scrap",
            json={
                "quantity": 1.0,
                "reason": "material_defect",
                "create_replacement": False,
                **_SEEDED_VERSIONS,
            },
            headers=owner_headers,
        )
        assert scrap_b.status_code == 200, scrap_b.text

        response = await client.get(
            f"{KPI_BASE}/scrap-by-reason",
            params=_period(tenant_today()),
            headers=await auth_headers(viewer),
        )
        assert response.status_code == 200, response.text
        rows = response.json()["rows"]

        # Total scrapped 3.0 (2.0 + 1.0): tool_breakage 2/3, material_defect 1/3.
        by_reason = {row["reason"]: row for row in rows}
        assert by_reason["tool_breakage"]["quantity"] == 2.0
        assert by_reason["tool_breakage"]["share"]["value"] == pytest.approx(2.0 / 3.0)
        assert by_reason["material_defect"]["quantity"] == 1.0
        assert by_reason["material_defect"]["share"]["value"] == pytest.approx(1.0 / 3.0)
        # Sorted descending by quantity.
        assert [row["reason"] for row in rows] == ["tool_breakage", "material_defect"]

    async def test_empty_period_returns_empty_rows(self, db: Session, client, viewer: User) -> None:
        response = await client.get(
            f"{KPI_BASE}/scrap-by-reason",
            params={"date_from": "2020-01-01", "date_to": "2020-01-01"},
            headers=await auth_headers(viewer),
        )
        assert response.status_code == 200, response.text
        assert response.json()["rows"] == []


class TestRejectedPerSupplierEndpoint:
    async def test_delivered_rejected_and_lost_quantity_per_supplier(
        self, db: Session, client, receiver: User, viewer: User
    ) -> None:
        supplier_a = await _supplier(db, receiver.id, "Supplier A")
        supplier_b = await _supplier(db, receiver.id, "Supplier B")
        item_a = await _seed_virtual_order_item(
            db, receiver.id, supplier_a.id, order_number="ORD-SKPI-A", quantity=10.0
        )
        item_b = await _seed_virtual_order_item(
            db, receiver.id, supplier_b.id, order_number="ORD-SKPI-B", quantity=5.0
        )
        receiver_headers = await auth_headers(receiver)

        # Supplier A: 8 accepted, 2 rejected (lost).
        response_a = await client.put(
            f"{DELIVER_URL}/{item_a}/deliver",
            params={"quantity": 8.0},
            json={
                "quantity_rejected": 2.0,
                "rejection_reason": "supplier_damage",
                "rejection_outcome": "lost",
                "create_replacement": False,
            },
            headers=receiver_headers,
        )
        assert response_a.status_code == 200, response_a.text

        # Supplier B: 5 accepted, nothing rejected.
        response_b = await client.put(
            f"{DELIVER_URL}/{item_b}/deliver", params={"quantity": 5.0}, headers=receiver_headers
        )
        assert response_b.status_code == 200, response_b.text

        response = await client.get(
            f"{KPI_BASE}/rejected-per-supplier",
            params=_period(tenant_today()),
            headers=await auth_headers(viewer),
        )
        assert response.status_code == 200, response.text
        rows = response.json()["rows"]
        by_name = {row["supplier_name"]: row for row in rows}

        row_a = by_name["Supplier A"]
        assert row_a["delivered"] == 8.0
        assert row_a["rejected"] == 2.0
        assert row_a["rejected_lost"] == 2.0
        # 2 rejected / (8 delivered + 2 rejected) = 0.2
        assert row_a["rejected_ratio"]["value"] == pytest.approx(0.2)

        row_b = by_name["Supplier B"]
        assert row_b["delivered"] == 5.0
        assert row_b["rejected"] == 0.0
        assert row_b["rejected_lost"] == 0.0
        assert row_b["rejected_ratio"]["value"] == pytest.approx(0.0)

    async def test_empty_period_returns_empty_rows(self, db: Session, client, viewer: User) -> None:
        response = await client.get(
            f"{KPI_BASE}/rejected-per-supplier",
            params={"date_from": "2020-01-01", "date_to": "2020-01-01"},
            headers=await auth_headers(viewer),
        )
        assert response.status_code == 200, response.text
        assert response.json()["rows"] == []
