"""
GET /external-work, the procurement list of external work, against the
throwaway SQLite database: which positions count as external work (an
EXTERNAL position on a supplier line, an UNASSIGNED one whose method is
usually outsourced, not one whose method is done in house), the order by
latest pickup, and the method, supplier-only, critical and search filters.
The dates the schedule walk writes are set on the rows directly, since the
walk itself is covered by the scheduling tests.
"""

from datetime import UTC
from datetime import date
from datetime import datetime
from datetime import timedelta

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
from src.modules.catalogue.domain.value_objects.step_role import StepRole
from src.modules.fulfillment.adapters.outbound.persistence.models.lot_position_model import (
    LotPositionOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.production_lot_repository.lot import (
    SqlAlchemyProductionLotRepository,
)
from src.modules.fulfillment.domain.entities.admin_settings.production import (
    AdminProductionSettings,
)
from src.modules.fulfillment.domain.entities.lot_position import LotPosition
from src.modules.fulfillment.domain.entities.lot_step import LotStep
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionKind
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionStatus
from src.modules.fulfillment.ports.outbound.repositories.production_lot_repository import (
    ExternalWorkFilterDto,
)
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.value_objects.permission import Permission
from src.modules.workspace.adapters.outbound.persistence.repositories.project_repository import (
    SqlAlchemyProjectRepository,
)
from src.modules.workspace.domain.entities.project import Project
from tests.integration import _lifecycle_seed as seed
from tests.integration._lot_facts import give_lot_facts

BASE = "/api/v1/web/external-work"
LOTS = "/api/v1/web/production-lots"


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
    return await create_user(username="external-work-owner", email="external-work@example.com")


@pytest.fixture
async def made_item_and_project(db: Session, owner: User) -> tuple[int, int]:
    project = await SqlAlchemyProjectRepository(db).save(
        Project(id=0, created=datetime.now(UTC), creator_id=owner.id, project_number="P-EXT-1")
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
            article_name="Guide rail",
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


async def _method(client, name: str, *, outsourced: bool) -> int:
    resp = await client.post(
        "/api/v1/web/fabrication-methods/",
        json={"name": {"enGB": name}, "required_external": outsourced, "lead_time_days": 4},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


async def _lot(client, made_item_id: int, project_id: int) -> dict:
    resp = await client.post(
        f"{LOTS}/",
        json={"made_item_id": made_item_id, "project_id": project_id, "quantity": 10.0},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _position(
    db: Session,
    owner: User,
    lot_id: int,
    sequence: int,
    kind: LotPositionKind,
    method_id: int,
) -> int:
    repo = SqlAlchemyProductionLotRepository(db)
    position = await repo.save_position(
        LotPosition(
            id=0,
            created=datetime.now(UTC),
            changed=None,
            changes=[],
            sequence=sequence,
            kind=kind,
            status=LotPositionStatus.PENDING,
            quantity=10.0,
            quantity_completed=0.0,
            note=None,
            creator_id=owner.id,
            lot_id=lot_id,
        )
    )
    await repo.save_step(
        LotStep(
            id=0,
            created=datetime.now(UTC),
            note=None,
            estimated_setup_minutes=None,
            estimated_minutes_per_piece=None,
            sequence=sequence,
            creator_id=owner.id,
            fabrication_method_id=method_id,
            lot_id=lot_id,
            position_id=position.id,
            source_process_id=None,
            role=StepRole.FABRICATION,
        )
    )
    # Committed, so the API's own session can write the next lot.
    await db.commit()
    return position.id


async def _dates(
    db: Session, position_id: int, *, planned_pickup: date, latest_pickup: date, lead_days: int = 4
) -> None:
    """The dates the schedule walk writes, set after the last write through
    the API, whose own walk would date the rows from the fixture's lots."""
    row = await db.get(LotPositionOrmModel, position_id)
    assert row is not None
    row.planned_pickup_date = planned_pickup
    row.latest_pickup_date = latest_pickup
    row.latest_delivery_date = latest_pickup + timedelta(days=lead_days)


@pytest.fixture
async def scenario(auth_client, made_item_and_project, owner: User, db: Session):
    """Lot A: milling done in house, then hardening without a supplier
    that cannot be ready by its latest pickup. Lot B: hardening already on
    a supplier's draft order, due later."""
    made_item_id, project_id = made_item_and_project
    client = await auth_client(
        permissions=[Permission.WRITE_LOTS, Permission.WRITE_FABRICATION_METHODS]
    )
    milling = await _method(client, "Milling (external work test)", outsourced=False)
    hardening = await _method(client, "Hardening (external work test)", outsourced=True)

    lot_a = await _lot(client, made_item_id, project_id)
    milling_position = await _position(
        db, owner, lot_a["id"], 1, LotPositionKind.UNASSIGNED, milling
    )
    unassigned = await _position(db, owner, lot_a["id"], 2, LotPositionKind.UNASSIGNED, hardening)

    lot_b = await _lot(client, made_item_id, project_id)
    ordered = await _position(db, owner, lot_b["id"], 1, LotPositionKind.EXTERNAL, hardening)
    purchase = await seed.order(db, "draft")
    await seed.line(db, purchase, "pending", at=await db.get(LotPositionOrmModel, ordered))
    await give_lot_facts(db, lot_a["id"], lot_b["id"])
    await _dates(db, unassigned, planned_pickup=date(2030, 3, 12), latest_pickup=date(2030, 3, 10))
    await _dates(db, ordered, planned_pickup=date(2030, 3, 20), latest_pickup=date(2030, 3, 25))
    await db.commit()
    return {
        "client": client,
        "lots": (lot_a, lot_b),
        "positions": {"milling": milling_position, "unassigned": unassigned, "ordered": ordered},
        "methods": {"milling": milling, "hardening": hardening},
    }


async def test_the_list_shows_external_work_by_latest_pickup(scenario) -> None:
    body = (await scenario["client"].get(f"{BASE}/")).json()

    positions = scenario["positions"]
    assert [row["position_id"] for row in body["items"]] == [
        positions["unassigned"],
        positions["ordered"],
    ]
    assert body["total"] == 2
    unassigned, ordered = body["items"]
    assert unassigned["latest_pickup_date"] == "2030-03-10"
    assert unassigned["back_by_date"] == "2030-03-14"
    assert unassigned["back_by_source"] == "latest_pickup"
    assert unassigned["alert"] == "not_ready_in_time"
    assert unassigned["order_item_id"] is None
    assert [m["id"] for m in unassigned["fabrication_methods"]] == [
        scenario["methods"]["hardening"]
    ]
    assert ordered["order_item_id"] is not None
    assert ordered["order_number"].startswith("OS-")
    assert ordered["lot_number"] == scenario["lots"][1]["lot_number"]
    assert ordered["project_number"] == "P-EXT-1"
    assert ordered["product_number"] is None


async def test_only_with_supplier_leaves_out_work_nobody_has_ordered(scenario) -> None:
    body = (await scenario["client"].get(f"{BASE}/", params={"only_with_supplier": True})).json()

    assert [row["position_id"] for row in body["items"]] == [scenario["positions"]["ordered"]]


async def test_only_critical_keeps_the_work_that_cannot_be_ready_in_time(scenario) -> None:
    body = (await scenario["client"].get(f"{BASE}/", params={"only_critical": True})).json()

    assert [row["position_id"] for row in body["items"]] == [scenario["positions"]["unassigned"]]


async def test_the_method_filter_and_the_search_narrow_the_list(scenario) -> None:
    client = scenario["client"]
    by_milling = (
        await client.get(
            f"{BASE}/", params={"fabrication_method_id": scenario["methods"]["milling"]}
        )
    ).json()
    by_lot = (
        await client.get(f"{BASE}/", params={"search": scenario["lots"][1]["lot_number"]})
    ).json()

    assert by_milling["items"] == []
    assert [row["position_id"] for row in by_lot["items"]] == [scenario["positions"]["ordered"]]


async def test_the_repository_finds_the_lots_the_walk_forecasts(scenario, db: Session) -> None:
    lot_a, lot_b = scenario["lots"]

    assert await SqlAlchemyProductionLotRepository(db).get_ids_with_external_work() == sorted(
        [lot_a["id"], lot_b["id"]]
    )


async def test_the_stage_filter_tells_unassigned_from_ordered_work(scenario) -> None:
    client = scenario["client"]
    positions = scenario["positions"]

    unassigned = (await client.get(f"{BASE}/", params={"stages": ["unassigned"]})).json()
    pending = (await client.get(f"{BASE}/", params={"stages": ["pending"]})).json()
    both = (await client.get(f"{BASE}/", params={"stages": ["unassigned", "pending"]})).json()

    assert [r["position_id"] for r in unassigned["items"]] == [positions["unassigned"]]
    assert [r["position_id"] for r in pending["items"]] == [positions["ordered"]]
    assert both["total"] == 2


async def test_the_alert_filter_finds_the_work_that_cannot_be_ready_in_time(scenario) -> None:
    body = (
        await scenario["client"].get(f"{BASE}/", params={"alerts": ["not_ready_in_time"]})
    ).json()

    assert [r["position_id"] for r in body["items"]] == [scenario["positions"]["unassigned"]]


async def test_the_lot_project_part_and_ready_filters_narrow_the_list(scenario) -> None:
    client = scenario["client"]
    lot_a, lot_b = scenario["lots"]
    positions = scenario["positions"]

    by_lot = (await client.get(f"{BASE}/", params={"lot_ids": [lot_b["id"]]})).json()
    by_project = (
        await client.get(f"{BASE}/", params={"project_ids": [lot_a["project_id"]]})
    ).json()
    by_part = (await client.get(f"{BASE}/", params={"part": "guide"})).json()
    by_ready = (
        await client.get(f"{BASE}/", params={"ready_from": "2030-03-15", "ready_to": "2030-03-31"})
    ).json()

    assert [r["position_id"] for r in by_lot["items"]] == [positions["ordered"]]
    assert by_project["total"] == 2
    assert by_part["total"] == 2
    assert [r["position_id"] for r in by_ready["items"]] == [positions["ordered"]]


async def test_a_row_names_its_supplier_by_id(scenario) -> None:
    body = (await scenario["client"].get(f"{BASE}/", params={"only_with_supplier": True})).json()

    [ordered] = body["items"]
    assert ordered["supplier_id"] == 1
    assert ordered["product_id"] is None


async def test_the_back_by_filter_reads_the_latest_delivery_without_a_supplier_date(
    scenario,
) -> None:
    """Hardening without a supplier is back by the 14th, the ordered one,
    whose line has no supplier date, by the 29th."""
    body = (
        await scenario["client"].get(
            f"{BASE}/", params={"back_by_from": "2030-03-20", "back_by_to": "2030-03-31"}
        )
    ).json()

    assert [r["position_id"] for r in body["items"]] == [scenario["positions"]["ordered"]]
    assert body["items"][0]["back_by_date"] == "2030-03-29"


async def test_the_product_filter_keeps_only_lots_of_that_product(scenario) -> None:
    body = (await scenario["client"].get(f"{BASE}/", params={"product_ids": [999]})).json()

    assert body["items"] == []


async def test_the_repository_filters_by_any_of_several_methods(scenario, db: Session) -> None:
    """The infoscreen widget narrows to several methods at once."""
    repo = SqlAlchemyProductionLotRepository(db)
    methods = scenario["methods"]

    _, both = await repo.get_external_work_page(
        ExternalWorkFilterDto(
            today=date(2030, 3, 1),
            fabrication_method_ids=[methods["milling"], methods["hardening"]],
        )
    )
    _, milling = await repo.get_external_work_page(
        ExternalWorkFilterDto(today=date(2030, 3, 1), fabrication_method_ids=[methods["milling"]])
    )

    assert len(both) == 2
    assert milling == []
