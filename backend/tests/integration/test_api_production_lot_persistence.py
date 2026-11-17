"""
Proves that the production lot write routes persist what they report.
Editing a lot, adding, reordering and deleting steps, recording a
provision, and the project time budget that a project edit, a step edit, a
structure save or a production order cancel spreads over the lot's steps
are each read back through a separate
request, so a use case that forgets to commit its unit of work fails here
instead of silently losing the write.
"""

from datetime import UTC
from datetime import date
from datetime import datetime
from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
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
from src.modules.fulfillment.adapters.outbound.persistence.repositories.production_order_repository import (
    SqlAlchemyProductionOrderRepository,
)
from src.modules.fulfillment.domain.entities.admin_settings.production import (
    AdminProductionSettings,
)
from src.modules.fulfillment.domain.entities.lot_position import LotPosition
from src.modules.fulfillment.domain.entities.lot_step import LotStep
from src.modules.fulfillment.domain.entities.production_order import ProductionOrder
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionKind
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionStatus
from src.modules.fulfillment.domain.value_objects.production_status import ProductionOrderStatus
from src.modules.fulfillment.domain.value_objects.production_status import UrgencyClass
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.value_objects.permission import Permission
from src.modules.workspace.adapters.outbound.persistence.repositories.project_repository import (
    SqlAlchemyProjectRepository,
)
from src.modules.workspace.domain.entities.project import Project
from tests.integration import _lifecycle_seed as seed
from tests.integration._edit_versions import lot_version
from tests.integration._edit_versions import production_order_version
from tests.integration._edit_versions import row_version
from tests.integration._lot_facts import give_lot_facts
from tests.integration.test_api_production_lots import _create_lot

BASE = "/api/v1/web/production-lots"


@pytest.fixture(autouse=True)
async def _seed_settings(db: Session) -> None:
    """CreateLot reads both the made-items (lot numbering) and production
    (order numbering / QA defaults) admin-settings domains; neither is in
    `_seed_admin_settings` (conftest.py). Mirrors InitDatabase's defaults."""
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
            default_external_lead_days=0,
            response_time_days=1,
            require_qa=False,
        )
    )
    await db.commit()


@pytest.fixture
async def made_item_and_project(db: Session, owner: User) -> tuple[int, int]:
    project = await SqlAlchemyProjectRepository(db).save(
        Project(id=0, created=datetime.now(UTC), creator_id=owner.id, project_number="P-LOT-1")
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
            article_name="Lot surface part",
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


@pytest.fixture
async def owner(create_user) -> User:
    return await create_user(username="lot-owner", email="lot-owner@example.com")


@pytest.fixture
async def planner(auth_client) -> Any:
    return await auth_client(
        permissions=[
            Permission.WRITE_LOTS,
            Permission.WRITE_FABRICATION_METHODS,
            Permission.MANAGE_PROJECTS,
            Permission.WRITE_PRODUCTION_ORDERS,
            Permission.MANAGE_PRODUCTION_ORDERS,
        ]
    )


async def _fabrication_method(client: Any, name: str, *, external: bool = False) -> int:
    response = await client.post(
        "/api/v1/web/fabrication-methods/",
        json={"name": {"enGB": name}, "required_external": external},
    )
    assert response.status_code == 201, response.text
    return int(response.json()["id"])


async def _reread(client: Any, lot_id: int) -> dict[str, Any]:
    response = await client.get(f"{BASE}/{lot_id}")
    assert response.status_code == 200, response.text
    return dict(response.json())


async def _seed_position(
    db: AsyncSession, lot_id: int, creator_id: int, kind: LotPositionKind, method_id: int
) -> tuple[int, list[int]]:
    """A position of the given kind with two steps, one estimated and one
    without an estimate, written straight through the repository because
    the routes only produce INTERNAL and EXTERNAL positions through a full
    machine or supplier assignment. The kind comes from what it is
    assigned: an INTERNAL position gets a queued production order and an
    EXTERNAL one a pending purchase line, and the lifecycle reconciler then
    stores what they derive."""
    repo = SqlAlchemyProductionLotRepository(db)
    position = await repo.save_position(
        LotPosition(
            id=0,
            created=datetime.now(UTC),
            changed=None,
            changes=[],
            sequence=1,
            kind=kind,
            status=LotPositionStatus.PENDING,
            quantity=10.0,
            quantity_completed=0.0,
            note=None,
            creator_id=creator_id,
            lot_id=lot_id,
        )
    )
    step_ids = []
    for sequence, minutes in ((1, None), (2, 5.0)):
        step = await repo.save_step(
            LotStep(
                id=0,
                created=datetime.now(UTC),
                note=None,
                estimated_setup_minutes=None,
                estimated_minutes_per_piece=minutes,
                sequence=sequence,
                creator_id=creator_id,
                fabrication_method_id=method_id,
                lot_id=lot_id,
                position_id=position.id,
                source_process_id=None,
                role=StepRole.FABRICATION,
            )
        )
        step_ids.append(step.id)
    if kind is LotPositionKind.INTERNAL:
        await _queue_production_order(db, position.id, creator_id)
    elif kind is LotPositionKind.EXTERNAL:
        purchase = await seed.order(db, "draft")
        await seed.line(db, purchase, "pending", at=await db.get(LotPositionOrmModel, position.id))
    # The lot the route created moves with the position just assigned.
    await give_lot_facts(db, lot_id, exact=False)
    await db.commit()
    return position.id, step_ids


async def _queue_production_order(
    db: AsyncSession, position_id: int, creator_id: int
) -> ProductionOrder:
    return await SqlAlchemyProductionOrderRepository(db).save(
        ProductionOrder(
            id=0,
            created=datetime.now(UTC),
            changed=None,
            changes=[],
            production_order_number=f"PO-PERSIST-{position_id}",
            status=ProductionOrderStatus.QUEUED,
            priority=UrgencyClass.NORMAL,
            pinned=False,
            queue_sequence=1,
            quantity=10.0,
            quantity_completed=0.0,
            estimated_duration_minutes=10,
            note=None,
            planned_start=None,
            planned_end=None,
            not_before=None,
            actual_start=None,
            actual_end=None,
            creator_id=creator_id,
            machine_id=None,
            lot_position_id=position_id,
        )
    )


async def test_lot_and_step_writes_are_persisted(
    planner, made_item_and_project: tuple[int, int]
) -> None:
    made_item_id, project_id = made_item_and_project
    lot_id = (await _create_lot(planner, made_item_id, project_id))["id"]
    method_id = await _fabrication_method(planner, "Milling (persistence test)")

    updated = await planner.patch(
        f"{BASE}/{lot_id}",
        json={"note": "Rush", "expected_edit_version": await lot_version(planner, lot_id)},
    )
    assert updated.status_code == 200, updated.text
    assert (await _reread(planner, lot_id))["note"] == "Rush"

    appended = await planner.post(
        f"{BASE}/{lot_id}/positions", json={"steps": [{"fabrication_method_id": method_id}]}
    )
    assert appended.status_code == 201, appended.text
    position_id = appended.json()["id"]
    first_step_id = appended.json()["steps"][0]["id"]

    added = await planner.post(
        f"{BASE}/{lot_id}/steps",
        json={"position_id": position_id, "fabrication_method_id": method_id, "note": "Deburr"},
    )
    assert added.status_code == 201, added.text
    second_step_id = added.json()["id"]
    steps = (await _reread(planner, lot_id))["steps"]
    assert [s["id"] for s in sorted(steps, key=lambda s: s["sequence"])] == [
        first_step_id,
        second_step_id,
    ]

    reordered = await planner.put(
        f"{BASE}/{lot_id}/steps/reorder",
        json={"ordered_step_ids": [second_step_id, first_step_id]},
    )
    assert reordered.status_code == 200, reordered.text
    steps = (await _reread(planner, lot_id))["steps"]
    assert [s["id"] for s in sorted(steps, key=lambda s: s["sequence"])] == [
        second_step_id,
        first_step_id,
    ]

    deleted = await planner.delete(f"{BASE}/{lot_id}/steps/{second_step_id}")
    assert deleted.status_code == 204, deleted.text
    steps = (await _reread(planner, lot_id))["steps"]
    assert [(s["id"], s["sequence"]) for s in steps] == [(first_step_id, 1)]


async def test_provision_is_persisted(
    planner, db, owner: User, made_item_and_project: tuple[int, int]
) -> None:
    made_item_id, project_id = made_item_and_project
    lot_id = (await _create_lot(planner, made_item_id, project_id))["id"]
    method_id = await _fabrication_method(planner, "Plating (persistence test)", external=True)
    position_id, _ = await _seed_position(db, lot_id, owner.id, LotPositionKind.EXTERNAL, method_id)

    recorded = await planner.post(
        f"{BASE}/{lot_id}/positions/{position_id}/provisions",
        json={"quantity": 4, "provision_date": date.today().isoformat()},
    )
    assert recorded.status_code == 201, recorded.text
    provisions = await planner.get(f"{BASE}/{lot_id}/positions/{position_id}/provisions")
    assert provisions.status_code == 200, provisions.text
    assert [p["quantity"] for p in provisions.json()] == [4]


async def test_time_budget_writes_are_persisted(
    planner, db, owner: User, made_item_and_project: tuple[int, int]
) -> None:
    made_item_id, project_id = made_item_and_project
    lot_id = (await _create_lot(planner, made_item_id, project_id))["id"]
    method_id = await _fabrication_method(planner, "Turning (persistence test)")
    _, (unestimated_id, estimated_id) = await _seed_position(
        db, lot_id, owner.id, LotPositionKind.INTERNAL, method_id
    )
    project = await SqlAlchemyProjectRepository(db).get_by_id(project_id)
    assert project is not None

    async def budgets() -> dict[int, float | None]:
        steps = (await _reread(planner, lot_id))["steps"]
        return {s["id"]: s["time_budget_per_piece"] for s in steps}

    # Only steps without their own estimate on an INTERNAL or MIXED position
    # share the project's budget, spread over the lot quantity of 10.
    project_updated = await planner.put(
        f"/api/v1/web/projects/{project_id}",
        json={
            "expected_edit_version": await row_version(
                planner, f"/api/v1/web/projects/{project_id}"
            ),
            "project_number": project.project_number,
            "production_time_budget": 200,
        },
    )
    assert project_updated.status_code == 200, project_updated.text
    assert await budgets() == {unestimated_id: 20.0, estimated_id: None}

    step_updated = await planner.patch(
        f"{BASE}/{lot_id}/steps/{estimated_id}",
        json={"fabrication_method_id": method_id, "estimated_minutes_per_piece": None},
    )
    assert step_updated.status_code == 200, step_updated.text
    assert await budgets() == {unestimated_id: 10.0, estimated_id: 10.0}


async def test_structure_save_persists_the_time_budget_it_spreads(
    planner, db, owner: User, made_item_and_project: tuple[int, int]
) -> None:
    made_item_id, project_id = made_item_and_project
    lot_id = (await _create_lot(planner, made_item_id, project_id))["id"]
    method_id = await _fabrication_method(planner, "Grinding (persistence test)")
    _, (unestimated_id, estimated_id) = await _seed_position(
        db, lot_id, owner.id, LotPositionKind.INTERNAL, method_id
    )
    # A budget set behind the routes' back, so the structure save below is
    # the first write that spreads it over the steps.
    projects = SqlAlchemyProjectRepository(db)
    project = await projects.get_by_id(project_id)
    assert project is not None
    project.production_time_budget = 200
    await projects.save(project)
    await db.commit()

    saved = await planner.put(
        f"{BASE}/{lot_id}/structure",
        json={
            "positions": [
                {
                    "steps": [
                        {"id": unestimated_id, "fabrication_method_id": method_id},
                        {
                            "id": estimated_id,
                            "fabrication_method_id": method_id,
                            "estimated_minutes_per_piece": 5.0,
                        },
                    ]
                }
            ]
        },
    )
    assert saved.status_code == 200, saved.text
    steps = (await _reread(planner, lot_id))["steps"]
    assert {s["id"]: s["time_budget_per_piece"] for s in steps} == {
        unestimated_id: 20.0,
        estimated_id: None,
    }


async def test_order_cancel_persists_the_time_budget_it_withdraws(
    planner, db, owner: User, made_item_and_project: tuple[int, int]
) -> None:
    made_item_id, project_id = made_item_and_project
    lot_id = (await _create_lot(planner, made_item_id, project_id))["id"]
    method_id = await _fabrication_method(planner, "Honing (persistence test)")
    position_id, (unestimated_id, estimated_id) = await _seed_position(
        db, lot_id, owner.id, LotPositionKind.INTERNAL, method_id
    )
    (order,) = await SqlAlchemyProductionOrderRepository(db).get_by_lot_position_id(position_id)
    project = await SqlAlchemyProjectRepository(db).get_by_id(project_id)
    assert project is not None
    budgeted = await planner.put(
        f"/api/v1/web/projects/{project_id}",
        json={
            "expected_edit_version": await row_version(
                planner, f"/api/v1/web/projects/{project_id}"
            ),
            "project_number": project.project_number,
            "production_time_budget": 200,
        },
    )
    assert budgeted.status_code == 200, budgeted.text

    # Canceling the position's only order sends it back to UNASSIGNED, which
    # takes its steps out of the project's budget pool.
    canceled = await planner.post(
        f"/api/v1/web/production-orders/{order.id}/cancel",
        json={"expected_edit_version": await production_order_version(planner, order.id)},
    )
    assert canceled.status_code == 200, canceled.text
    steps = (await _reread(planner, lot_id))["steps"]
    assert {s["id"]: s["time_budget_per_piece"] for s in steps} == {
        unestimated_id: None,
        estimated_id: None,
    }


async def test_lot_cancel_persists_the_time_budget_it_withdraws(
    planner, auth_client, db, owner: User, made_item_and_project: tuple[int, int]
) -> None:
    made_item_id, project_id = made_item_and_project
    lot_id = (await _create_lot(planner, made_item_id, project_id))["id"]
    method_id = await _fabrication_method(planner, "Lapping (persistence test)")
    _position_id, (unestimated_id, estimated_id) = await _seed_position(
        db, lot_id, owner.id, LotPositionKind.INTERNAL, method_id
    )
    project = await SqlAlchemyProjectRepository(db).get_by_id(project_id)
    assert project is not None
    budgeted = await planner.put(
        f"/api/v1/web/projects/{project_id}",
        json={
            "expected_edit_version": await row_version(
                planner, f"/api/v1/web/projects/{project_id}"
            ),
            "project_number": project.project_number,
            "production_time_budget": 200,
        },
    )
    assert budgeted.status_code == 200, budgeted.text
    assert (await _reread(planner, lot_id))["steps"][0]["time_budget_per_piece"] is not None

    # A canceled lot's positions go back to UNASSIGNED, which takes their
    # steps out of the project's budget pool.
    manager = await auth_client(
        username="lot-manager",
        email="lot-manager@example.com",
        permissions=[Permission.WRITE_LOTS, Permission.MANAGE_LOTS],
    )
    canceled = await manager.post(
        f"/api/v1/web/production-lots/{lot_id}/cancel",
        json={"expected_edit_version": await lot_version(planner, lot_id)},
    )
    assert canceled.status_code == 200, canceled.text
    steps = (await _reread(planner, lot_id))["steps"]
    assert {s["id"]: s["time_budget_per_piece"] for s in steps} == {
        unestimated_id: None,
        estimated_id: None,
    }
