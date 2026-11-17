"""
HTTP-level round trip for the computed machine status field on
ProductionMachineResponse (idle, running, paused, down, and the
precedence between an open downtime and an active order). Prerequisites
(project, made item, lot, position, machines, orders) are seeded directly
through the real repositories, the same pattern
test_api_production_order_time_tracking.py uses; only the router under
test goes through HTTP.
"""

from datetime import UTC
from datetime import datetime

import pytest
from sqlalchemy.orm import Session

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
from src.modules.fulfillment.domain.entities.lot_position import LotPosition
from src.modules.fulfillment.domain.entities.production_lot import ProductionLot
from src.modules.fulfillment.domain.entities.production_machine import ProductionMachine
from src.modules.fulfillment.domain.entities.production_order import ProductionOrder
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionKind
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionStatus
from src.modules.fulfillment.domain.value_objects.lot_status import LotStatus
from src.modules.fulfillment.domain.value_objects.machine_downtime_reason import (
    MachineDowntimeReason,
)
from src.modules.fulfillment.domain.value_objects.production_status import ProductionOrderStatus
from src.modules.fulfillment.domain.value_objects.production_status import UrgencyClass
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.value_objects.permission import Permission
from src.modules.workspace.adapters.outbound.persistence.repositories.project_repository import (
    SqlAlchemyProjectRepository,
)
from src.modules.workspace.domain.entities.project import Project
from tests.integration._lot_facts import give_position_lot_facts
from tests.integration._production_order_facts import give_production_order_facts
from tests.integration.conftest import auth_headers

MACHINES_BASE = "/api/v1/web/production-machines"


async def _seed_machine(db: Session, creator_id: int, internal_name: str) -> ProductionMachine:
    saved = await SqlAlchemyProductionMachineRepository(db).save(
        ProductionMachine(
            id=0,
            created=datetime.now(UTC).date(),
            changed=None,
            changes=[],
            archived=False,
            internal_name=internal_name,
            vendor="Contoso",
            model="VF-2",
            fabrication_method_ids=[],
            max_part_dimension=None,
            note=None,
            creator_id=creator_id,
        )
    )
    await db.commit()
    return saved


async def _seed_lot_position(db: Session, creator_id: int, *, lot_number: str) -> LotPosition:
    """One lot/position pair every seeded order in a test attaches to;
    the status computation only cares about machine_id/order status, not
    which lot a given order belongs to."""
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
            article_name="Machine status test part",
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
            quantity=5.0,
            status=LotStatus.PLANNED,
            priority=UrgencyClass.NORMAL,
            note=None,
            creator_id=creator_id,
            made_item_id=made_item.id,
            project_id=project.id,
            input_demand_id=None,
        )
    )
    return await lot_repo.save_position(
        LotPosition(
            id=0,
            created=datetime.now(UTC),
            changed=None,
            changes=[],
            sequence=1,
            kind=LotPositionKind.INTERNAL,
            status=LotPositionStatus.ORDERED_OR_QUEUED,
            quantity=5.0,
            quantity_completed=0.0,
            note=None,
            creator_id=creator_id,
            lot_id=lot.id,
        )
    )


async def _seed_order(
    db: Session,
    creator_id: int,
    *,
    number: str,
    machine_id: int,
    lot_position_id: int,
    status: ProductionOrderStatus,
) -> ProductionOrder:
    saved = await SqlAlchemyProductionOrderRepository(db).save(
        ProductionOrder(
            id=0,
            created=datetime.now(UTC),
            changed=None,
            changes=[],
            production_order_number=number,
            status=status,
            priority=UrgencyClass.NORMAL,
            pinned=False,
            queue_sequence=1,
            quantity=5.0,
            quantity_completed=0.0,
            estimated_duration_minutes=30,
            note=None,
            planned_start=None,
            planned_end=None,
            not_before=None,
            actual_start=datetime.now(UTC),
            actual_end=None,
            creator_id=creator_id,
            machine_id=machine_id,
            lot_position_id=lot_position_id,
        )
    )
    await give_production_order_facts(db, saved.id)
    # The seeded planned lot moves with the order just added.
    await give_position_lot_facts(db, lot_position_id, exact=False)
    await db.commit()
    return saved


@pytest.fixture
async def viewer(create_user) -> User:
    return await create_user(
        username="status-viewer", email="status-viewer@example.com", permissions=[]
    )


@pytest.fixture
async def operator(create_user) -> User:
    return await create_user(
        username="status-operator",
        email="status-operator@example.com",
        permissions=[Permission.WRITE_MACHINES],
    )


class TestMachineStatusOnList:
    async def test_idle_running_paused_and_down_resolve_independently(
        self, db: Session, client, viewer: User
    ) -> None:
        position = await _seed_lot_position(db, viewer.id, lot_number="STATUS-LOT-1")
        idle_machine = await _seed_machine(db, viewer.id, "STATUS-IDLE")
        running_machine = await _seed_machine(db, viewer.id, "STATUS-RUNNING")
        paused_machine = await _seed_machine(db, viewer.id, "STATUS-PAUSED")
        await _seed_order(
            db,
            viewer.id,
            number="PO-RUN-1",
            machine_id=running_machine.id,
            lot_position_id=position.id,
            status=ProductionOrderStatus.IN_PROGRESS,
        )
        await _seed_order(
            db,
            viewer.id,
            number="PO-PAUSE-1",
            machine_id=paused_machine.id,
            lot_position_id=position.id,
            status=ProductionOrderStatus.PAUSED,
        )

        listing = await client.get(MACHINES_BASE, headers=await auth_headers(viewer))
        assert listing.status_code == 200
        by_id = {m["id"]: m for m in listing.json()["items"]}

        assert by_id[idle_machine.id]["status"] == "idle"
        assert by_id[idle_machine.id]["active_orders"] == []

        assert by_id[running_machine.id]["status"] == "running"
        running_orders = by_id[running_machine.id]["active_orders"]
        assert [o["production_order_number"] for o in running_orders] == ["PO-RUN-1"]
        assert running_orders[0]["status"] == "in_progress"

        assert by_id[paused_machine.id]["status"] == "paused"
        paused_orders = by_id[paused_machine.id]["active_orders"]
        assert [o["production_order_number"] for o in paused_orders] == ["PO-PAUSE-1"]

    async def test_open_downtime_reports_down_even_with_a_running_order(
        self, db: Session, client, operator: User
    ) -> None:
        position = await _seed_lot_position(db, operator.id, lot_number="STATUS-LOT-2")
        machine = await _seed_machine(db, operator.id, "STATUS-DOWN")
        await _seed_order(
            db,
            operator.id,
            number="PO-DOWN-1",
            machine_id=machine.id,
            lot_position_id=position.id,
            status=ProductionOrderStatus.IN_PROGRESS,
        )
        headers = await auth_headers(operator)

        added = await client.post(
            f"{MACHINES_BASE}/downtimes",
            json={
                "machine_id": machine.id,
                "started_at": "2026-01-01T08:00:00Z",
                "reason": MachineDowntimeReason.BREAKDOWN.value,
            },
            headers=headers,
        )
        assert added.status_code == 201

        listing = await client.get(MACHINES_BASE, headers=headers)
        row = next(m for m in listing.json()["items"] if m["id"] == machine.id)
        assert row["status"] == "down"
        assert row["open_downtime"] is not None


class TestMachineStatusOnDetail:
    async def test_detail_endpoint_reports_the_same_status_as_the_list(
        self, db: Session, client, viewer: User
    ) -> None:
        position = await _seed_lot_position(db, viewer.id, lot_number="STATUS-LOT-3")
        machine = await _seed_machine(db, viewer.id, "STATUS-DETAIL-RUNNING")
        await _seed_order(
            db,
            viewer.id,
            number="PO-DETAIL-1",
            machine_id=machine.id,
            lot_position_id=position.id,
            status=ProductionOrderStatus.IN_PROGRESS,
        )

        detail = await client.get(
            f"{MACHINES_BASE}/{machine.id}", headers=await auth_headers(viewer)
        )
        assert detail.status_code == 200
        body = detail.json()
        assert body["status"] == "running"
        assert [o["production_order_number"] for o in body["active_orders"]] == ["PO-DETAIL-1"]
