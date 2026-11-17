"""
HTTP-level coverage for deleting a lot position that is still
referenced by an order item's `lot_position_id` (a real, NO ACTION FK,
see production_lot_repository/lot.py's delete_position docstring) must
surface as a clean 409, not an unhandled IntegrityError/500. The unit
tests (tests/unit/production_lot/) prove the use-case guard raises
LotPositionInUseError against a fake repository; this proves the real DI
graph wires IOrderItemRepository through and the exception maps to 409
over the actual HTTP boundary.

The position is seeded with kind=UNASSIGNED even though an order item
already points at it, normally impossible through the application (kind
tracks the FK via assign_external_position.py), but exactly the gap the
guard exists to catch defensively: it must not rely solely on `kind`
being in sync.
"""

from datetime import UTC
from datetime import date
from datetime import datetime

from src.modules.catalogue.adapters.outbound.persistence.repositories.fabrication_method_repository import (
    SqlAlchemyFabricationMethodRepository,
)
from src.modules.catalogue.adapters.outbound.persistence.repositories.made_item_repository.item import (
    SqlAlchemyMadeItemRepository,
)
from src.modules.catalogue.adapters.outbound.persistence.repositories.supplier_repository import (
    SqlAlchemySupplierRepository,
)
from src.modules.catalogue.domain.entities.fabrication_method import FabricationMethod
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
from src.modules.fulfillment.domain.entities.lot_position import LotPosition
from src.modules.fulfillment.domain.entities.lot_step import LotStep
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
from src.modules.platform.const import API_WEB
from src.modules.platform.domain.value_objects.localized_text import LocalizedText
from src.modules.platform.domain.value_objects.permission import Permission
from src.modules.workspace.adapters.outbound.persistence.repositories.project_repository import (
    SqlAlchemyProjectRepository,
)
from src.modules.workspace.domain.entities.project import Project

LOTS = f"{API_WEB}/production-lots"


async def _seed_lot_position_with_referencing_order_item(db, creator_id: int):
    project = await SqlAlchemyProjectRepository(db).save(
        Project(id=0, created=datetime.now(UTC), creator_id=creator_id, project_number="P-LPU-1")
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
            article_name="Lot-position-in-use part",
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
    method = await SqlAlchemyFabricationMethodRepository(db).save(
        FabricationMethod(
            id=0,
            created=datetime.now(UTC),
            changed=datetime.now(UTC),
            changes=[],
            archived=False,
            name=LocalizedText({"enGB": "LPU Turning"}),
            label_color="#000000",
            label_font_color="#ffffff",
            description=LocalizedText(),
            creator_id=creator_id,
        )
    )
    lot_repo = SqlAlchemyProductionLotRepository(db)
    lot = await lot_repo.save(
        ProductionLot(
            id=0,
            created=datetime.now(UTC),
            changed=None,
            changes=[],
            lot_number="LN-LPU-1",
            quantity=5.0,
            status=LotStatus.DRAFT,
            priority=UrgencyClass.NORMAL,
            note=None,
            creator_id=creator_id,
            made_item_id=made_item.id,
            project_id=project.id,
            input_demand_id=None,
        )
    )
    # kind=UNASSIGNED despite the order item link below: normally
    # impossible through the app (kind tracks the FK), but exactly the
    # gap the use-case guard defends against: it must not depend solely
    # on `kind` being correctly synced.
    position = await lot_repo.save_position(
        LotPosition(
            id=0,
            created=datetime.now(UTC),
            changed=None,
            changes=[],
            sequence=1,
            kind=LotPositionKind.UNASSIGNED,
            status=LotPositionStatus.PENDING,
            quantity=5.0,
            quantity_completed=0.0,
            note=None,
            creator_id=creator_id,
            lot_id=lot.id,
        )
    )
    step = await lot_repo.save_step(
        LotStep(
            id=0,
            created=datetime.now(UTC),
            note=None,
            estimated_setup_minutes=10,
            estimated_minutes_per_piece=2.0,
            sequence=1,
            creator_id=creator_id,
            fabrication_method_id=method.id,
            lot_id=lot.id,
            position_id=position.id,
            source_process_id=None,
        )
    )

    supplier = await SqlAlchemySupplierRepository(db).save(
        Supplier(
            id=0,
            created=datetime.now(UTC),
            changed=datetime.now(UTC),
            changes=[],
            archived=False,
            name="LPU Supplier",
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
    order = await SqlAlchemyOrderRepository(db).save(
        Order(
            id=0,
            order_number="ORD-LPU-1",
            created=date.today(),
            changed=None,
            changes=[],
            status=OrderStatus.DRAFT,
            note=None,
            ordered_date=None,
            expected_delivery_date=None,
            delivery_date=None,
            storage_place=None,
            creator_id=creator_id,
            supplier_id=supplier.id,
        )
    )
    await SqlAlchemyOrderItemRepository(db).save(
        OrderItem(
            id=0,
            created=datetime.now(UTC),
            changed=None,
            changes=[],
            status=OrderItemStatus.PENDING,
            quantity=5.0,
            quantity_delivered=0.0,
            unit="pcs",
            items_per_unit=1.0,
            price=None,
            note=None,
            ordered_date=None,
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
            supplier_id=supplier.id,
            project_id=project.id,
            line_type=OrderLineType.MADE,
            lot_position_id=position.id,
            source_item_id=None,
            virtual_name=None,
        )
    )
    await db.commit()
    return lot, position, step


class TestDeleteLotStepPositionInUse:
    async def test_deleting_the_last_step_of_a_referenced_position_returns_409(
        self, db, auth_client, allow_lifecycle_drift
    ):
        """The seeded kind disagrees with the order item on purpose, see the
        module docstring, and the refused delete leaves it so."""
        client = await auth_client(permissions=[Permission.WRITE_LOTS])
        lot, _position, step = await _seed_lot_position_with_referencing_order_item(
            db, creator_id=1
        )

        response = await client.delete(f"{LOTS}/{lot.id}/steps/{step.id}")

        assert response.status_code == 409

    async def test_rejected_delete_leaves_the_step_in_place(
        self, db, auth_client, allow_lifecycle_drift
    ):
        """The seeded kind disagrees with the order item on purpose, see the
        module docstring, and the refused delete leaves it so."""
        client = await auth_client(permissions=[Permission.WRITE_LOTS])
        lot, _position, step = await _seed_lot_position_with_referencing_order_item(
            db, creator_id=1
        )

        response = await client.delete(f"{LOTS}/{lot.id}/steps/{step.id}")

        assert response.status_code == 409
        db.expire_all()
        lots = SqlAlchemyProductionLotRepository(db)
        assert await lots.get_step_by_id(step.id) is not None
        assert not [e for e in await lots.get_events(lot.id) if e.entity_id == step.id]

    async def test_deleting_the_last_step_of_an_unreferenced_position_succeeds(
        self, db, auth_client
    ):
        """Control case: same shape, no order item link. The guard must
        not block the ordinary path."""
        client = await auth_client(permissions=[Permission.WRITE_LOTS])
        lot, position, step = await _seed_lot_position_with_referencing_order_item(db, creator_id=1)
        # Detach the order item created by the helper so this position is
        # genuinely unreferenced.
        order_item_repo = SqlAlchemyOrderItemRepository(db)
        blocking = await order_item_repo.get_by_lot_position_id(position.id)
        assert blocking is not None
        await order_item_repo.delete(blocking)
        await db.commit()

        response = await client.delete(f"{LOTS}/{lot.id}/steps/{step.id}")

        assert response.status_code == 204
