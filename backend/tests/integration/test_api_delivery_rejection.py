"""
HTTP-level round trip for rejecting pieces while booking a delivery
(PUT /bought-items-allocations/order-item/{id}/deliver and
PUT /orders/{id}/deliver-all-items). Prerequisites are seeded directly
through the real repositories, the same pattern test_api_scrap_pieces.py
and test_api_delivery_permission.py use; only the routers under test go
through HTTP.
"""

from datetime import UTC
from datetime import datetime

import pytest
from sqlalchemy import update
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
from src.modules.fulfillment.adapters.outbound.persistence.models.production_lot_model import (
    ProductionLotOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.order_repository.order import (
    SqlAlchemyOrderRepository,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.order_repository.order_item import (
    SqlAlchemyOrderItemRepository,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.production_lot_repository.lot import (
    SqlAlchemyProductionLotRepository,
)
from src.modules.fulfillment.domain.entities.admin_settings.production import (
    AdminProductionSettings,
)
from src.modules.fulfillment.domain.entities.lot_position import LotPosition
from src.modules.fulfillment.domain.entities.order import Order
from src.modules.fulfillment.domain.entities.order_item import OrderItem
from src.modules.fulfillment.domain.entities.production_lot import ProductionLot
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionKind
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionStatus
from src.modules.fulfillment.domain.value_objects.lot_status import LotStatus
from src.modules.fulfillment.domain.value_objects.order_status import OrderItemStatus
from src.modules.fulfillment.domain.value_objects.order_status import OrderLineType
from src.modules.fulfillment.domain.value_objects.order_status import OrderStatus
from src.modules.fulfillment.domain.value_objects.production_status import UrgencyClass
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.value_objects.permission import Permission
from src.modules.workspace.adapters.outbound.persistence.repositories.project_repository import (
    SqlAlchemyProjectRepository,
)
from src.modules.workspace.domain.entities.project import Project

DELIVER_URL = "/api/v1/web/bought-items-allocations/order-item"
DELIVER_ALL_URL = "/api/v1/web/orders"
LOTS_BASE = "/api/v1/web/production-lots"


@pytest.fixture(autouse=True)
async def _seed_production_settings(db: Session) -> None:
    """A MADE-line "lost" disposition may spawn a replacement lot through
    the real CreateLot use case, which needs admin production settings
    seeded; mirrors test_api_scrap_pieces.py's own fixture."""
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


async def _seed_virtual_order_item(db: Session, *, quantity: float = 2.0) -> tuple[int, int]:
    """One order with one VIRTUAL line (no catalogue/supplier setup
    needed, see OrderItem.line_type's docstring), returns (order_id,
    item_id)."""
    order = await SqlAlchemyOrderRepository(db).save(
        Order(
            id=0,
            order_number="ORD-REJ-0001",
            created=datetime.now(UTC),
            changed=None,
            changes=[],
            status=OrderStatus.ORDERED,
            note=None,
            ordered_date=datetime.now(UTC),
            expected_delivery_date=None,
            delivery_date=None,
            storage_place=None,
            creator_id=1,
            supplier_id=1,
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
            expected_delivery_date=datetime(2026, 10, 1).date(),
            delivery_date=None,
            storage_place=None,
            expected_pickup_date=None,
            ready_for_pickup_date=None,
            position=1,
            creator_id=1,
            orderer_id=None,
            receiver_id=None,
            bought_item_id=None,
            order_id=order.id,
            supplier_id=1,
            project_id=1,
            line_type=OrderLineType.VIRTUAL,
            lot_position_id=None,
            source_item_id=None,
            virtual_name="Freight",
        )
    )
    await db.commit()
    return order.id, item.id


async def _seed_made_line(
    db: Session, creator_id: int, *, lot_number: str, quantity: float = 2.0
) -> tuple[ProductionLot, int, int]:
    """One lot with a single EXTERNAL position and the OrderItem assigned
    to it, mirroring assign_external_position.py's own invariants.
    Returns (lot, order_id, item_id)."""
    project = await SqlAlchemyProjectRepository(db).save(
        Project(id=0, created=datetime.now(UTC), creator_id=creator_id, project_number=lot_number)
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
            article_name="Goods receipt rejection test part",
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
        )
    )
    position = await lot_repo.save_position(
        LotPosition(
            id=0,
            created=datetime.now(UTC),
            changed=None,
            changes=[],
            sequence=1,
            kind=LotPositionKind.EXTERNAL,
            status=LotPositionStatus.ORDERED_OR_QUEUED,
            quantity=quantity,
            quantity_completed=0.0,
            note=None,
            creator_id=creator_id,
            lot_id=lot.id,
        )
    )
    order = await SqlAlchemyOrderRepository(db).save(
        Order(
            id=0,
            order_number=f"{lot_number}-ORD",
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
            supplier_id=1,
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
            expected_delivery_date=None,
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
            supplier_id=1,
            project_id=project.id,
            line_type=OrderLineType.MADE,
            lot_position_id=position.id,
            source_item_id=None,
            virtual_name=None,
        )
    )
    await db.commit()
    return lot, order.id, item.id


@pytest.fixture
async def receiver(auth_client):
    return await auth_client(permissions=[Permission.RECEIVE_DELIVERIES])


@pytest.fixture
async def owner(create_user) -> User:
    return await create_user(
        username="reject-owner",
        email="reject-owner@example.com",
        permissions=[Permission.RECEIVE_DELIVERIES],
    )


class TestDeliverOrderItemRejection:
    async def test_missing_reason_or_outcome_returns_422(self, db: Session, receiver) -> None:
        _order_id, item_id = await _seed_virtual_order_item(db)

        response = await receiver.put(
            f"{DELIVER_URL}/{item_id}/deliver",
            params={"quantity": 1.0},
            json={"quantity_rejected": 1.0},
        )

        assert response.status_code == 422, response.text
        assert response.json()["code"] == "DeliveryRejectionInvalidError"

    @pytest.mark.parametrize(
        "rejection",
        [
            {"quantity_rejected": 0, "rejection_outcome": "redeliver"},
            {"rejection_reason": "transport_damage"},
        ],
    )
    async def test_a_reason_or_outcome_without_rejected_pieces_returns_422(
        self, db: Session, receiver, rejection: dict[str, object]
    ) -> None:
        _order_id, item_id = await _seed_virtual_order_item(db, quantity=2.0)

        response = await receiver.put(
            f"{DELIVER_URL}/{item_id}/deliver", params={"quantity": 1.0}, json=rejection
        )

        assert response.status_code == 422, response.text
        assert response.json()["code"] == "DeliveryRejectionInvalidError"

    async def test_over_capacity_rejection_returns_422(self, db: Session, receiver) -> None:
        _order_id, item_id = await _seed_virtual_order_item(db, quantity=2.0)

        response = await receiver.put(
            f"{DELIVER_URL}/{item_id}/deliver",
            params={"quantity": 1.0},
            json={
                "quantity_rejected": 5.0,
                "rejection_reason": "transport_damage",
                "rejection_outcome": "lost",
            },
        )

        assert response.status_code == 422, response.text
        assert response.json()["code"] == "InvalidDeliveryQuantityError"

    async def test_redeliver_clears_expected_delivery_date_and_keeps_line_open(
        self, db: Session, receiver
    ) -> None:
        _order_id, item_id = await _seed_virtual_order_item(db, quantity=2.0)

        response = await receiver.put(
            f"{DELIVER_URL}/{item_id}/deliver",
            params={"quantity": 1.0},
            json={
                "quantity_rejected": 1.0,
                "rejection_reason": "transport_damage",
                "rejection_outcome": "redeliver",
            },
        )

        assert response.status_code == 200, response.text
        body = response.json()
        assert body["quantity_delivered"] == 1.0
        assert body["quantity_rejected"] == 1.0
        assert body["quantity_rejected_lost"] == 0.0
        assert body["expected_delivery_date"] is None
        assert body["status"] == "partially_delivered"

    async def test_lost_outcome_on_non_made_line_covers_the_line(
        self, db: Session, receiver
    ) -> None:
        _order_id, item_id = await _seed_virtual_order_item(db, quantity=2.0)

        response = await receiver.put(
            f"{DELIVER_URL}/{item_id}/deliver",
            params={"quantity": 1.0},
            json={
                "quantity_rejected": 1.0,
                "rejection_reason": "transport_damage",
                "rejection_outcome": "lost",
            },
        )

        assert response.status_code == 200, response.text
        body = response.json()
        assert body["quantity_delivered"] == 1.0
        assert body["quantity_rejected_lost"] == 1.0
        # delivered (1) + rejected_lost (1) == quantity (2): fulfilled.
        assert body["status"] == "delivered"

    async def test_lost_outcome_on_made_line_closes_lot_short_and_creates_replacement(
        self, db: Session, receiver, owner: User
    ) -> None:
        lot, _order_id, item_id = await _seed_made_line(
            db, owner.id, lot_number="LOT-REJ-1", quantity=2.0
        )

        response = await receiver.put(
            f"{DELIVER_URL}/{item_id}/deliver",
            params={"quantity": 1.0},
            json={
                "quantity_rejected": 1.0,
                "rejection_reason": "supplier_damage",
                "rejection_outcome": "lost",
                "create_replacement": True,
            },
        )

        assert response.status_code == 200, response.text
        body = response.json()
        assert body["quantity_delivered"] == 1.0
        assert body["quantity_rejected_lost"] == 1.0
        assert body["status"] == "delivered"

        lot_response = await receiver.get(f"{LOTS_BASE}/{lot.id}")
        assert lot_response.status_code == 200, lot_response.text
        lot_body = lot_response.json()
        assert lot_body["quantity"] == 1.0
        assert lot_body["quantity_scrapped"] == 1.0
        assert lot_body["status"] == "completed"
        assert len(lot_body["replacement_lot_ids"]) == 1

    async def test_lost_outcome_with_create_replacement_false_skips_lot_creation(
        self, db: Session, receiver, owner: User
    ) -> None:
        lot, _order_id, item_id = await _seed_made_line(
            db, owner.id, lot_number="LOT-REJ-2", quantity=2.0
        )

        response = await receiver.put(
            f"{DELIVER_URL}/{item_id}/deliver",
            params={"quantity": 0.0},
            json={
                "quantity_rejected": 2.0,
                "rejection_reason": "supplier_damage",
                "rejection_outcome": "lost",
                "create_replacement": False,
            },
        )

        assert response.status_code == 200, response.text

        lot_response = await receiver.get(f"{LOTS_BASE}/{lot.id}")
        assert lot_response.status_code == 200, lot_response.text
        lot_body = lot_response.json()
        assert lot_body["quantity"] == 0.0
        assert lot_body["quantity_scrapped"] == 2.0
        assert lot_body["status"] == "scrapped"
        assert lot_body["replacement_lot_ids"] == []

    async def test_a_held_lot_lost_to_zero_ends_without_its_hold(
        self, db: Session, receiver, owner: User
    ) -> None:
        lot, _order_id, item_id = await _seed_made_line(
            db, owner.id, lot_number="LOT-REJ-HELD", quantity=2.0
        )
        await db.execute(
            update(ProductionLotOrmModel)
            .where(ProductionLotOrmModel.id == lot.id)
            .values(held_at=datetime.now(UTC))
        )
        await db.commit()

        response = await receiver.put(
            f"{DELIVER_URL}/{item_id}/deliver",
            params={"quantity": 0.0},
            json={
                "quantity_rejected": 2.0,
                "rejection_reason": "supplier_damage",
                "rejection_outcome": "lost",
                "create_replacement": False,
            },
        )

        assert response.status_code == 200, response.text
        lot_body = (await receiver.get(f"{LOTS_BASE}/{lot.id}")).json()
        assert lot_body["status"] == "scrapped"
        assert lot_body["held_at"] is None


class TestDeliverAllOrderItemsRejection:
    async def test_per_line_rejection_is_booked_alongside_the_rest(
        self, db: Session, receiver
    ) -> None:
        order_id, item_id = await _seed_virtual_order_item(db, quantity=2.0)

        response = await receiver.put(
            f"{DELIVER_ALL_URL}/{order_id}/deliver-all-items",
            json={
                "rejections": [
                    {
                        "order_item_id": item_id,
                        "quantity_rejected": 1.0,
                        "rejection_reason": "wrong_spec",
                        "rejection_outcome": "redeliver",
                    }
                ]
            },
        )

        assert response.status_code == 200, response.text
        [item] = response.json()["delivered"]
        assert item["quantity_rejected"] == 1.0
        assert item["quantity_delivered"] == 1.0
        assert item["expected_delivery_date"] is None
        assert item["status"] == "partially_delivered"
