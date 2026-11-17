"""
HTTP-level round trip for POST /production-lots/{id}/print, the scrap_tag
classifier's lot-scoped manual print action. Prerequisites (project, made
item, lot, position, machine, order) are seeded directly through the real
repositories, the same pattern test_api_scrap_pieces.py uses; the scrap
booking itself goes through the real POST /production-orders/{id}/scrap
endpoint so the completion this test resolves from is the genuine article.

No print_template row is seeded (print_template_table is only populated by
a migration, which integration tests never run, see database skill), so
every print here resolves its root correctly but fails at the "no
template configured" step; that failure is itself the proof the endpoint
picked the right classifier/root_type/root_id, the same restraint
test_api_printers.py documents for not touching a real network device.
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
from tests.integration.conftest import auth_headers

ORDERS_BASE = "/api/v1/web/production-orders"
LOTS_BASE = "/api/v1/web/production-lots"


@pytest.fixture(autouse=True)
async def _seed_production_settings(db: Session) -> None:
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
            article_name="Scrap tag test part",
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
    db: Session, creator_id: int, *, lot_number: str, quantity: float = 3.0
) -> tuple[ProductionLot, ProductionOrder]:
    project = await SqlAlchemyProjectRepository(db).save(
        Project(id=0, created=datetime.now(UTC), creator_id=creator_id, project_number=lot_number)
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
            status=LotStatus.PLANNED,
            priority=UrgencyClass.NORMAL,
            note=None,
            creator_id=creator_id,
            made_item_id=made_item.id,
            project_id=project.id,
            input_demand_id=None,
            # Rework lot, exempt from the sequence-1 raw-material gating
            # StartProductionOrder otherwise applies (same fixture trick as
            # test_api_scrap_pieces.py).
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
    return lot, order


@pytest.fixture
async def owner(create_user) -> User:
    return await create_user(
        username="scrap-tag-owner",
        email="scrap-tag-owner@example.com",
        permissions=[Permission.WRITE_PRODUCTION_ORDERS, Permission.PRINT_DOCUMENTS],
    )


class TestPrintLotScrapTagEndpoint:
    async def test_resolves_the_scrap_completion_and_reaches_the_print_pipeline(
        self, db: Session, client, owner: User
    ) -> None:
        lot, order = await _seed_lot_and_order(db, owner.id, lot_number="LOT-STAG-1")
        headers = await auth_headers(owner)

        started = await client.post(f"{ORDERS_BASE}/{order.id}/start", json={}, headers=headers)
        assert started.status_code == 200

        scrapped = await client.post(
            f"{ORDERS_BASE}/{order.id}/scrap",
            json={
                "quantity": 3.0,
                "reason": "tool_breakage",
                "create_replacement": True,
                "expected_edit_version": order.edit_version,
                "expected_lot_edit_version": lot.edit_version,
            },
            headers=headers,
        )
        assert scrapped.status_code == 200, scrapped.text

        completions = await SqlAlchemyProductionOrderRepository(db).get_completions(order.id)
        assert len(completions) == 1

        response = await client.post(f"{LOTS_BASE}/{lot.id}/print", json={}, headers=headers)
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["classifier"] == "scrap_tag"
        assert body["root_type"] == "production_order_completion"
        assert body["root_id"] == completions[0].id
        # No print_template row exists in the test DB (see module
        # docstring): the pipeline still ran and recorded a failed job
        # rather than raising, proving the resolution itself succeeded.
        assert body["status"] == "failed"
        assert body["trigger"] == "manual"

    async def test_requires_print_documents_permission(
        self, db: Session, client, create_user
    ) -> None:
        actor = await create_user(
            username="scrap-tag-no-print",
            email="scrap-tag-no-print@example.com",
            permissions=[Permission.WRITE_PRODUCTION_ORDERS],
        )
        lot, order = await _seed_lot_and_order(db, actor.id, lot_number="LOT-STAG-2")
        headers = await auth_headers(actor)
        await client.post(f"{ORDERS_BASE}/{order.id}/start", json={}, headers=headers)
        await client.post(
            f"{ORDERS_BASE}/{order.id}/scrap",
            json={
                "quantity": 3.0,
                "reason": "tool_breakage",
                "create_replacement": False,
                "expected_edit_version": order.edit_version,
                "expected_lot_edit_version": lot.edit_version,
            },
            headers=headers,
        )

        response = await client.post(f"{LOTS_BASE}/{lot.id}/print", json={}, headers=headers)
        assert response.status_code == 403

    async def test_404_when_the_lot_has_no_scrap_record(
        self, db: Session, client, owner: User
    ) -> None:
        lot, _order = await _seed_lot_and_order(db, owner.id, lot_number="LOT-STAG-3")
        response = await client.post(
            f"{LOTS_BASE}/{lot.id}/print", json={}, headers=await auth_headers(owner)
        )
        assert response.status_code == 404
        assert response.json()["code"] == "ScrapTagRecordNotFoundError"

    async def test_404_for_a_missing_lot(self, client, owner: User) -> None:
        response = await client.post(
            f"{LOTS_BASE}/999999/print", json={}, headers=await auth_headers(owner)
        )
        assert response.status_code == 404
