"""
HTTP-level round trip for the KPI data-foundation fields added to the
production order and lot surfaces: planned_end_at_start, interruptions,
the completion disposition quantities, and lot completed_at. Prerequisites
(project, made item, lot, position, machine, order) are seeded directly
through the real repositories, the same pattern test_api_production_orders.py
uses; only the router under test goes through HTTP. The seeded lot is a
rework lot (source_made_item_id set) so StartProductionOrder's sequence-1
raw-material gating doesn't apply, mirroring the unit tests' own fixture
trick.
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
from tests.integration._tenant_day import tenant_today
from tests.integration.conftest import auth_headers

ORDERS_BASE = "/api/v1/web/production-orders"
LOTS_BASE = "/api/v1/web/production-lots"


@pytest.fixture(autouse=True)
async def _seed_production_settings(db: Session) -> None:
    """RecordProductionOrderCompletion tries a schedule recompute after
    commit; mirrors test_api_production_orders.py's own fixture."""
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
            article_name="KPI time-tracking part",
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
    db: Session, creator_id: int, *, lot_number: str, quantity: float = 5.0
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
        username="kpi-owner",
        email="kpi-owner@example.com",
        permissions=[Permission.WRITE_PRODUCTION_ORDERS],
    )


class TestStartPauseResumeCancelFields:
    async def test_baseline_and_interruptions_round_trip_over_http(
        self, db: Session, client, owner: User
    ) -> None:
        _lot, order = await _seed_lot_and_order(db, owner.id, lot_number="LOT-TT-1")
        headers = await auth_headers(owner)

        started = await client.post(f"{ORDERS_BASE}/{order.id}/start", json={}, headers=headers)
        assert started.status_code == 200
        body = started.json()
        assert body["status"] == ProductionOrderStatus.IN_PROGRESS.value
        assert body["planned_end_at_start"] is not None
        baseline = body["planned_end_at_start"]
        assert body["interruptions"] == []

        paused = await client.post(f"{ORDERS_BASE}/{order.id}/pause", json={}, headers=headers)
        assert paused.status_code == 200
        assert paused.json()["status"] == ProductionOrderStatus.PAUSED.value

        after_pause = await client.get(f"{ORDERS_BASE}/{order.id}", headers=headers)
        interruptions = after_pause.json()["interruptions"]
        assert len(interruptions) == 1
        assert interruptions[0]["resumed_at"] is None

        resumed = await client.post(f"{ORDERS_BASE}/{order.id}/start", json={}, headers=headers)
        assert resumed.status_code == 200
        resumed_body = resumed.json()
        assert resumed_body["status"] == ProductionOrderStatus.IN_PROGRESS.value
        # Baseline is frozen once, a resume must not rewrite it.
        assert resumed_body["planned_end_at_start"] == baseline
        assert len(resumed_body["interruptions"]) == 1
        assert resumed_body["interruptions"][0]["resumed_at"] is not None

        canceled = await client.post(
            f"{ORDERS_BASE}/{order.id}/cancel",
            json={"expected_edit_version": order.edit_version},
            headers=headers,
        )
        assert canceled.status_code == 200
        canceled_body = canceled.json()
        assert canceled_body["status"] == ProductionOrderStatus.CANCELED.value
        # A cancel keeps the baseline too.
        assert canceled_body["planned_end_at_start"] == baseline


class TestCompletionRoundTrip:
    async def test_completion_persists_disposition_fields_and_completes_the_lot(
        self, db: Session, client, owner: User
    ) -> None:
        lot, order = await _seed_lot_and_order(db, owner.id, lot_number="LOT-TT-2", quantity=5.0)
        headers = await auth_headers(owner)

        started = await client.post(f"{ORDERS_BASE}/{order.id}/start", json={}, headers=headers)
        assert started.status_code == 200

        completed = await client.post(
            f"{ORDERS_BASE}/{order.id}/completions",
            json={"quantity": 5.0, "completion_date": tenant_today().isoformat()},
            headers=headers,
        )
        assert completed.status_code == 200
        body = completed.json()
        assert body["status"] == ProductionOrderStatus.COMPLETED.value
        last_completion = body["completions"][-1]
        assert last_completion["quantity_rework"] == 0.0
        assert last_completion["quantity_scrap"] == 0.0

        lot_response = await client.get(f"{LOTS_BASE}/{lot.id}", headers=headers)
        assert lot_response.status_code == 200
        lot_body = lot_response.json()
        assert lot_body["status"] == LotStatus.COMPLETED.value
        assert lot_body["completed_at"] is not None
