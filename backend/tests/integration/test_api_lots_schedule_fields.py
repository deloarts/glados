"""
HTTP-level coverage for GET /production-lots' new read-model fields: an
internal production order's earliest_start_reason/earliest_start_date, an
external position's lead_days/lead_days_source, and a lot's
target_date/target_date_source/target_date_demand_item_id (see
_context.describe_lot_target_dates). All are computed by GetLots (see
get_lot.py) and exposed only on the summary-shaped LotSummaryResponse the
list endpoint returns. Setup mirrors test_api_production_lots.py
(project/made item seeded through the real repositories, the lot itself
created through the router).
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
from src.modules.catalogue.domain.entities.admin_settings.made_items import AdminMadeItemSettings
from src.modules.catalogue.domain.entities.made_item import MadeItem
from src.modules.catalogue.domain.policies.item_field_ownership import default_policy
from src.modules.catalogue.domain.value_objects.data_source import DataSource
from src.modules.catalogue.domain.value_objects.made_item_status import MadeItemCatalogueStatus
from src.modules.catalogue.domain.value_objects.made_item_status import MadeItemDemandStatus
from src.modules.catalogue.domain.value_objects.step_role import StepRole
from src.modules.fulfillment.adapters.outbound.persistence.models.lot_position_model import (
    LotPositionOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.made_item_demand_repository.allocation import (
    SqlAlchemyMadeItemAllocationRepository,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.made_item_demand_repository.demand_item import (
    SqlAlchemyMadeItemDemandItemRepository,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.production_lot_repository.lot import (
    SqlAlchemyProductionLotRepository,
)
from src.modules.fulfillment.domain.entities.admin_settings.production import (
    AdminProductionSettings,
)
from src.modules.fulfillment.domain.entities.lot_position import LotPosition
from src.modules.fulfillment.domain.entities.lot_step import LotStep
from src.modules.fulfillment.domain.entities.made_item_allocation import MadeItemDemandAllocation
from src.modules.fulfillment.domain.entities.made_item_demand_item import MadeItemDemandItem
from src.modules.fulfillment.domain.value_objects.lifecycle_aggregate import LifecycleAggregate
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionKind
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionStatus
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.value_objects.permission import Permission
from src.modules.workspace.adapters.outbound.persistence.repositories.project_repository import (
    SqlAlchemyProjectRepository,
)
from src.modules.workspace.domain.entities.project import Project
from tests.integration import _lifecycle_seed as seed
from tests.integration._demand_facts import give_demand_facts
from tests.integration._lot_facts import give_lot_facts

BASE = "/api/v1/web/production-lots"


@pytest.fixture(autouse=True)
async def _seed_settings(db: Session) -> None:
    repo = SqlAlchemyAdminSettingsRepository(db)
    await repo.save_made_items(
        AdminMadeItemSettings(
            id=1,
            item_number_format="FAB-{yy}-{seq:05d}",
            lot_number_format="LOT-{yy}-{seq:05d}",
            part_number_auto=True,
            part_number_editable=False,
            revision_start="0",
            revision_separator=":",
            revision_skip_ambiguous_letters=False,
            revision_only_newest_editable=True,
            revision_predecessor_status_web="ask",
            revision_predecessor_status_pdm="replaced",
            revision_field_policy=default_policy(),
            web_creation_allowed=True,
            pdm_part_number_pattern="",
        )
    )
    await db.commit()
    await repo.save_production(
        AdminProductionSettings(
            id=1,
            production_order_number_format="PON-{yy}-{seq:05d}",
            default_weekly_hours={0: 480, 1: 480, 2: 480, 3: 480, 4: 480, 5: 0, 6: 0},
            default_external_lead_days=1,
            response_time_days=1,
            require_qa=False,
        )
    )
    await db.commit()


@pytest.fixture
async def owner(create_user) -> User:
    return await create_user(username="lot-schedule-owner", email="lot-schedule-owner@example.com")


@pytest.fixture
async def made_item_and_project(db: Session, owner: User) -> tuple[int, int]:
    project = await SqlAlchemyProjectRepository(db).save(
        Project(id=0, created=datetime.now(UTC), creator_id=owner.id, project_number="P-SCHED-1")
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
            article_name="Lot schedule fields part",
            status=MadeItemCatalogueStatus.ACTIVE,
            data_source=DataSource.WEB,
            part_number=None,
            material=None,
            mass=None,
            base_size=None,
            note=None,
            weblink=None,
            files=[],
            creator_id=owner.id,
            approver_id=None,
            bought_item_id=None,
            source_item_id=None,
            article_group_ids=[],
            successor_item_id=None,
            changed_by_id=None,
        )
    )
    await db.commit()
    return made_item.id, project.id


async def _create_lot(client, made_item_id: int, project_id: int) -> dict:
    resp = await client.post(
        f"{BASE}/",
        json={"made_item_id": made_item_id, "project_id": project_id, "quantity": 10.0},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


async def test_lots_list_exposes_lead_days_for_an_external_position(
    auth_client, made_item_and_project: tuple[int, int], owner: User, db: Session
) -> None:
    made_item_id, project_id = made_item_and_project
    client = await auth_client(
        permissions=[Permission.WRITE_LOTS, Permission.WRITE_FABRICATION_METHODS]
    )

    fabrication_method = await client.post(
        "/api/v1/web/fabrication-methods/",
        json={
            "name": {"enGB": "Anodizing (schedule fields test)"},
            "required_external": True,
            "lead_time_days": 5,
        },
    )
    assert fabrication_method.status_code == 201, fabrication_method.text

    lot = await _create_lot(client, made_item_id, project_id)

    lot_repo = SqlAlchemyProductionLotRepository(db)
    position = await lot_repo.save_position(
        LotPosition(
            id=0,
            created=datetime.now(UTC),
            changed=None,
            changes=[],
            sequence=1,
            kind=LotPositionKind.EXTERNAL,
            status=LotPositionStatus.PENDING,
            quantity=10.0,
            quantity_completed=0.0,
            note=None,
            creator_id=owner.id,
            lot_id=lot["id"],
        )
    )
    await lot_repo.save_step(
        LotStep(
            id=0,
            created=datetime.now(UTC),
            note=None,
            estimated_setup_minutes=None,
            estimated_minutes_per_piece=None,
            sequence=1,
            creator_id=owner.id,
            fabrication_method_id=fabrication_method.json()["id"],
            lot_id=lot["id"],
            position_id=position.id,
            source_process_id=None,
            role=StepRole.FABRICATION,
        )
    )
    # EXTERNAL because a pending purchase line carries it.
    purchase = await seed.order(db, "draft")
    await seed.line(db, purchase, "pending", at=await db.get(LotPositionOrmModel, position.id))
    await give_lot_facts(db, lot["id"])
    await db.commit()

    resp = await client.get(f"{BASE}/")
    assert resp.status_code == 200
    body = resp.json()
    listed = next(item for item in body["items"] if item["id"] == lot["id"])
    listed_position = listed["positions"][0]
    assert listed_position["lead_days"] == 5
    assert listed_position["lead_days_source"] == "method"


async def test_lots_list_exposes_earliest_start_reason_for_an_unqueued_position(
    auth_client, made_item_and_project: tuple[int, int], owner: User, db: Session
) -> None:
    """A freshly-created lot has no position/order structure yet. This is covered
    separately by an UNASSIGNED position sitting with no production order
    at all, which resolves no orders and therefore no explanation entries
    (nothing to assert past "the field exists and defaults safely"). The
    lead-days test above already proves the position side of the wiring;
    this proves the endpoint doesn't 500 when a lot has positions but no
    production orders."""
    made_item_id, project_id = made_item_and_project
    lot_client = await auth_client(permissions=[Permission.WRITE_LOTS])
    lot = await _create_lot(lot_client, made_item_id, project_id)

    lot_repo = SqlAlchemyProductionLotRepository(db)
    await lot_repo.save_position(
        LotPosition(
            id=0,
            created=datetime.now(UTC),
            changed=None,
            changes=[],
            sequence=1,
            kind=LotPositionKind.UNASSIGNED,
            status=LotPositionStatus.PENDING,
            quantity=10.0,
            quantity_completed=0.0,
            note=None,
            creator_id=owner.id,
            lot_id=lot["id"],
        )
    )
    await db.commit()

    resp = await lot_client.get(f"{BASE}/")
    assert resp.status_code == 200
    body = resp.json()
    listed = next(item for item in body["items"] if item["id"] == lot["id"])
    listed_position = listed["positions"][0]
    assert listed_position["production_orders"] == []
    assert listed_position["lead_days"] is None
    assert listed_position["lead_days_source"] is None


async def test_lots_list_exposes_target_date_from_the_manual_required_delivery_date(
    auth_client, made_item_and_project: tuple[int, int]
) -> None:
    made_item_id, project_id = made_item_and_project
    client = await auth_client(permissions=[Permission.WRITE_LOTS])

    resp = await client.post(
        f"{BASE}/",
        json={
            "made_item_id": made_item_id,
            "project_id": project_id,
            "quantity": 10.0,
            "required_delivery_date": "2026-04-01",
        },
    )
    assert resp.status_code == 201, resp.text
    lot = resp.json()

    body = (await client.get(f"{BASE}/")).json()
    listed = next(item for item in body["items"] if item["id"] == lot["id"])
    assert listed["target_date"] == "2026-04-01"
    assert listed["target_date_source"] == "lot"
    assert listed["target_date_demand_item_id"] is None


async def test_lots_list_exposes_target_date_from_an_allocated_demand(
    auth_client, made_item_and_project: tuple[int, int], owner: User, db: Session
) -> None:
    """A lot with no manual required_delivery_date falls back to the
    earliest desired_delivery_date over the demand items it's allocated
    against (see _context.describe_lot_target_dates). The demand item and
    its allocation are written directly through the repositories, the
    same way this file's other tests attach a LotPosition/LotStep the
    create endpoint doesn't expose. It also sidesteps
    made_item_and_project's fixture MadeItem having a lowercase
    data_source="web", which 500s the made-items-demands POST endpoint's
    response validation (it embeds MadeItemResponse, whose data_source is
    the uppercase DataSource enum); unrelated to this WP, so worked around
    rather than fixed here."""
    made_item_id, project_id = made_item_and_project
    client = await auth_client(permissions=[Permission.WRITE_LOTS])

    demand = await SqlAlchemyMadeItemDemandItemRepository(db).save(
        MadeItemDemandItem(
            id=0,
            created=date(2026, 1, 1),
            changed=None,
            changes=[],
            status=MadeItemDemandStatus.OPEN,
            quantity=10.0,
            unit="pcs",
            items_per_unit=1.0,
            high_priority=False,
            notify_on_delivery=False,
            note=None,
            desired_delivery_date=date(2026, 5, 15),
            creator_id=owner.id,
            made_item_id=made_item_id,
            project_id=project_id,
        )
    )
    await db.commit()

    lot = await _create_lot(client, made_item_id, project_id)
    await SqlAlchemyMadeItemAllocationRepository(db).save(
        MadeItemDemandAllocation(demand_item_id=demand.id, lot_id=lot["id"], quantity=10.0)
    )
    await give_demand_facts(db, LifecycleAggregate.MADE_DEMANDS, demand.id, expected="allocated")
    await db.commit()

    body = (await client.get(f"{BASE}/")).json()
    listed = next(item for item in body["items"] if item["id"] == lot["id"])
    assert date.fromisoformat(listed["target_date"]) == date(2026, 5, 15)
    assert listed["target_date_source"] == "demand"
    assert listed["target_date_demand_item_id"] == demand.id
