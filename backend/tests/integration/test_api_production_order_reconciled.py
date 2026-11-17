"""
Production orders over HTTP on the throwaway SQLite file, with the lifecycle
reconciler deriving every order status from the recorded facts and intents,
and the drift check after each test confirming that every stored status
matches its derivation: start, pause, resume and completion of an order, a
lot hold and resume next to a pause made by hand, a force cancel and a force
completion of a lot with a paused order, the cancel of a made demand that
cancels its lot, a split of a pool order, a merge across pools, and rejects
outside an inspection. A drifted canceled order revived by the reconciler
takes a free queue place, which the partial unique indexes on queue_sequence
enforce on SQLite as well.
"""

import itertools
from datetime import UTC
from datetime import date
from datetime import datetime
from datetime import timedelta
from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.bootstrap.adapters.outbound.persistence.repositories.admin_settings_repository import (
    SqlAlchemyAdminSettingsRepository,
)
from src.modules.catalogue.adapters.outbound.persistence.repositories.made_item_repository.item import (
    SqlAlchemyMadeItemRepository,
)
from src.modules.catalogue.domain.entities.made_item import MadeItem
from src.modules.catalogue.domain.value_objects.data_source import DataSource
from src.modules.catalogue.domain.value_objects.made_item_status import MadeItemCatalogueStatus
from src.modules.catalogue.domain.value_objects.made_item_status import MadeItemDemandStatus
from src.modules.fulfillment.adapters.outbound.persistence.lifecycle_store import (
    sql_lifecycle_repositories,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.production_order_model import (
    ProductionOrderOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.machine_pool_repository import (
    SqlAlchemyMachinePoolRepository,
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
from src.modules.fulfillment.adapters.outbound.persistence.repositories.production_machine_repository import (
    SqlAlchemyProductionMachineRepository,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.production_order_repository import (
    SqlAlchemyProductionOrderRepository,
)
from src.modules.fulfillment.application.services.lifecycle_reconciler import LifecycleReconciler
from src.modules.fulfillment.domain.entities.admin_settings.production import (
    AdminProductionSettings,
)
from src.modules.fulfillment.domain.entities.lot_position import LotPosition
from src.modules.fulfillment.domain.entities.machine_pool import MachinePool
from src.modules.fulfillment.domain.entities.made_item_allocation import MadeItemDemandAllocation
from src.modules.fulfillment.domain.entities.made_item_demand_item import MadeItemDemandItem
from src.modules.fulfillment.domain.entities.production_lot import ProductionLot
from src.modules.fulfillment.domain.entities.production_machine import ProductionMachine
from src.modules.fulfillment.domain.entities.production_order import ProductionOrder
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionKind
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionStatus
from src.modules.fulfillment.domain.value_objects.lot_status import LotStatus
from src.modules.fulfillment.domain.value_objects.production_status import ProductionOrderStatus
from src.modules.fulfillment.domain.value_objects.production_status import UrgencyClass
from src.modules.platform.adapters.outbound.persistence.session import SessionLocal
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.value_objects.permission import Permission
from src.modules.workspace.adapters.outbound.persistence.repositories.project_repository import (
    SqlAlchemyProjectRepository,
)
from src.modules.workspace.domain.entities.project import Project
from tests.integration._edit_versions import lot_version
from tests.integration._tenant_day import tenant_today
from tests.integration.conftest import auth_headers

ORDERS = "/api/v1/web/production-orders"
LOTS = "/api/v1/web/production-lots"
MADE_DEMANDS = "/api/v1/web/made-items-demands"

_numbers = itertools.count(1)


class _Bus:
    def __init__(self) -> None:
        self.published: list[object] = []

    async def publish(self, event: object) -> None:
        self.published.append(event)


@pytest.fixture(autouse=True)
async def _seed_production_settings(db: AsyncSession) -> None:
    """Completion, split and merge read the production settings."""
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
async def planner(create_user) -> User:
    return await create_user(
        username="reconciled-planner",
        email="reconciled-planner@example.com",
        permissions=[
            Permission.WRITE_PRODUCTION_ORDERS,
            Permission.MANAGE_PRODUCTION_ORDERS,
            Permission.WRITE_LOTS,
            Permission.MANAGE_LOTS,
            Permission.WRITE_DEMAND_ITEMS,
            Permission.MANAGE_DEMAND_ITEMS,
        ],
    )


class _Floor:
    """One rework lot of 10 with one internal position, one machine, and the
    orders a test asks for; a rework lot never waits for raw material."""

    def __init__(self, db: AsyncSession, creator_id: int) -> None:
        self.db = db
        self.creator_id = creator_id
        self.project_id = 0
        self.made_item_id = 0
        self.lot_id = 0
        self.position_id = 0
        self.machine_id = 0

    async def build(self) -> "_Floor":
        n = next(_numbers)
        now = datetime.now(UTC)
        project = await SqlAlchemyProjectRepository(self.db).save(
            Project(id=0, created=now, creator_id=self.creator_id, project_number=f"P-REC-{n}")
        )
        item = await SqlAlchemyMadeItemRepository(self.db).save(
            MadeItem(
                id=0,
                created=now,
                changed=now,
                changes=[],
                archived=False,
                revision="0",
                revision_date=None,
                revision_note=None,
                article_name=f"Reconciled part {n}",
                status=MadeItemCatalogueStatus.ACTIVE,
                data_source=DataSource.WEB,
                part_number=None,
                material=None,
                mass=None,
                base_size=None,
                note=None,
                weblink=None,
                files=[],
                creator_id=self.creator_id,
                approver_id=None,
                bought_item_id=None,
                source_item_id=None,
                article_group_ids=[],
                successor_item_id=None,
                changed_by_id=None,
            )
        )
        await self.db.commit()
        lots = SqlAlchemyProductionLotRepository(self.db)
        lot = await lots.save(
            ProductionLot(
                id=0,
                created=now,
                changed=None,
                changes=[],
                lot_number=f"LN-REC-{n}",
                quantity=10.0,
                status=LotStatus.PLANNED,
                priority=UrgencyClass.NORMAL,
                note=None,
                creator_id=self.creator_id,
                made_item_id=item.id,
                project_id=project.id,
                input_demand_id=None,
                source_made_item_id=item.id,
            )
        )
        position = await lots.save_position(
            LotPosition(
                id=0,
                created=now,
                changed=None,
                changes=[],
                sequence=1,
                kind=LotPositionKind.INTERNAL,
                status=LotPositionStatus.ORDERED_OR_QUEUED,
                quantity=10.0,
                quantity_completed=0.0,
                note=None,
                creator_id=self.creator_id,
                lot_id=lot.id,
            )
        )
        machine = await self.machine(f"REC-MILL-{n}")
        self.project_id, self.made_item_id = project.id, item.id
        self.lot_id, self.position_id, self.machine_id = lot.id, position.id, machine
        await self.db.commit()
        return self

    async def machine(self, name: str) -> int:
        machine = await SqlAlchemyProductionMachineRepository(self.db).save(
            ProductionMachine(
                id=0,
                created=date.today(),
                changed=None,
                changes=[],
                archived=False,
                internal_name=name,
                vendor="Contoso",
                model="VF-2",
                fabrication_method_ids=[],
                max_part_dimension=None,
                note=None,
                creator_id=self.creator_id,
            )
        )
        await self.db.commit()
        return machine.id

    async def pool(self, name: str) -> int:
        pool = await SqlAlchemyMachinePoolRepository(self.db).save(
            MachinePool(
                id=0,
                created=date.today(),
                changed=None,
                changes=[],
                archived=False,
                name=name,
                machine_ids=[self.machine_id],
                note=None,
                creator_id=self.creator_id,
            )
        )
        await self.db.commit()
        return pool.id

    async def made_demand(self, quantity: float) -> int:
        """A made demand of the lot's part, covered in full by the lot."""
        demand = await SqlAlchemyMadeItemDemandItemRepository(self.db).save(
            MadeItemDemandItem(
                id=0,
                created=date.today(),
                changed=None,
                changes=[],
                status=MadeItemDemandStatus.ORDERED,
                quantity=quantity,
                unit="pcs",
                items_per_unit=1.0,
                high_priority=False,
                notify_on_delivery=False,
                note=None,
                desired_delivery_date=None,
                creator_id=self.creator_id,
                made_item_id=self.made_item_id,
                project_id=self.project_id,
            )
        )
        await SqlAlchemyMadeItemAllocationRepository(self.db).save(
            MadeItemDemandAllocation(
                demand_item_id=demand.id, lot_id=self.lot_id, quantity=quantity
            )
        )
        await self.db.commit()
        return demand.id

    async def order(self, quantity: float, queue_sequence: int, **values: Any) -> int:
        n = next(_numbers)
        values.setdefault("machine_id", self.machine_id)
        order = await SqlAlchemyProductionOrderRepository(self.db).save(
            ProductionOrder(
                id=0,
                created=datetime.now(UTC),
                changed=None,
                changes=[],
                production_order_number=f"PO-REC-{n}",
                status=values.pop("status", ProductionOrderStatus.QUEUED),
                priority=UrgencyClass.NORMAL,
                pinned=False,
                queue_sequence=queue_sequence,
                quantity=quantity,
                quantity_completed=0.0,
                estimated_duration_minutes=30,
                note=None,
                planned_start=None,
                planned_end=None,
                not_before=None,
                actual_start=None,
                actual_end=None,
                creator_id=self.creator_id,
                lot_position_id=self.position_id,
                **values,
            )
        )
        await self.db.commit()
        return order.id


async def _floor(db: AsyncSession, user: User) -> _Floor:
    return await _Floor(db, user.id).build()


async def _post(client, url: str, user: User, body: dict[str, Any] | None = None) -> Any:
    return await client.post(url, json=body or {}, headers=await auth_headers(user))


async def _order(client, order_id: int, user: User) -> dict[str, Any]:
    response = await client.get(f"{ORDERS}/{order_id}", headers=await auth_headers(user))
    assert response.status_code == 200, response.text
    return response.json()


async def test_start_pause_resume_and_completion_derive_each_status(
    db: AsyncSession, client, planner: User
) -> None:
    floor = await _floor(db, planner)
    order_id = await floor.order(5.0, 1)

    started = await _post(client, f"{ORDERS}/{order_id}/start", planner)
    assert started.status_code == 200, started.text
    assert started.json()["status"] == "in_progress"
    paused = await _post(client, f"{ORDERS}/{order_id}/pause", planner)
    assert paused.json()["status"] == "paused"
    resumed = await _post(client, f"{ORDERS}/{order_id}/start", planner)
    assert resumed.json()["status"] == "in_progress"
    assert resumed.json()["actual_start"] == started.json()["actual_start"]
    completed = await _post(
        client,
        f"{ORDERS}/{order_id}/completions",
        planner,
        {"quantity": 5.0, "completion_date": tenant_today().isoformat()},
    )
    assert completed.status_code == 200, completed.text

    body = await _order(client, order_id, planner)
    assert body["status"] == "completed"
    assert body["actual_end"] is not None
    assert [row["resumed_at"] is not None for row in body["interruptions"]] == [True]


async def test_a_lot_resume_leaves_an_order_paused_by_hand_paused(
    db: AsyncSession, client, planner: User
) -> None:
    floor = await _floor(db, planner)
    running = await floor.order(5.0, 1)
    paused_by_hand = await floor.order(5.0, 2)
    for order_id in (running, paused_by_hand):
        started = await _post(client, f"{ORDERS}/{order_id}/start", planner)
        assert started.status_code == 200, started.text
    await _post(client, f"{ORDERS}/{paused_by_hand}/pause", planner)

    held = await _post(client, f"{LOTS}/{floor.lot_id}/hold", planner, {"reason": "Material"})
    assert held.status_code == 200, held.text
    assert (await _order(client, running, planner))["status"] == "paused"
    resumed = await _post(client, f"{LOTS}/{floor.lot_id}/resume", planner)
    assert resumed.status_code == 200, resumed.text

    running_body = await _order(client, running, planner)
    by_hand_body = await _order(client, paused_by_hand, planner)
    assert running_body["status"] == "in_progress"
    assert [r["reason"] for r in running_body["interruptions"]] == ["lot_hold"]
    assert running_body["interruptions"][0]["resumed_at"] is not None
    assert by_hand_body["status"] == "paused"
    assert [(r["reason"], r["resumed_at"]) for r in by_hand_body["interruptions"]] == [
        ("manual", None)
    ]


@pytest.mark.parametrize(("action", "ended"), [("cancel", "canceled"), ("complete", "completed")])
async def test_forcing_the_lot_ends_a_paused_order_and_its_pause(
    db: AsyncSession, client, planner: User, action: str, ended: str
) -> None:
    floor = await _floor(db, planner)
    order_id = await floor.order(10.0, 1)
    await _post(client, f"{ORDERS}/{order_id}/start", planner)
    if action == "complete":
        # A force-complete needs pieces produced and ends the order at them.
        recorded = await _post(
            client,
            f"{ORDERS}/{order_id}/completions",
            planner,
            {"quantity": 4.0, "completion_date": tenant_today().isoformat()},
        )
        assert recorded.status_code == 200, recorded.text
    await _post(client, f"{ORDERS}/{order_id}/pause", planner)

    version = await lot_version(client, floor.lot_id, await auth_headers(planner))
    forced = await _post(
        client, f"{LOTS}/{floor.lot_id}/{action}", planner, {"expected_edit_version": version}
    )
    assert forced.status_code == 200, forced.text

    body = await _order(client, order_id, planner)
    assert body["status"] == ended
    assert [row["resumed_at"] is not None for row in body["interruptions"]] == [True]


async def test_canceling_a_made_demand_cancels_the_running_and_paused_orders_of_its_lot(
    db: AsyncSession, client, planner: User
) -> None:
    """The made demand's cancel drives the lot's force cancel, which only
    registers the orders it cancels; they end canceled only because both
    share the request's one reconciler."""
    floor = await _floor(db, planner)
    running = await floor.order(5.0, 1)
    paused = await floor.order(5.0, 2)
    for order_id in (running, paused):
        started = await _post(client, f"{ORDERS}/{order_id}/start", planner)
        assert started.status_code == 200, started.text
    await _post(client, f"{ORDERS}/{paused}/pause", planner)
    demand_id = await floor.made_demand(10.0)

    canceled = await client.put(
        f"{MADE_DEMANDS}/{demand_id}/status",
        params={"new_status": "canceled"},
        headers=await auth_headers(planner),
    )

    assert canceled.status_code == 200, canceled.text
    assert canceled.json()["status"] == "canceled"
    lot = await client.get(f"{LOTS}/{floor.lot_id}", headers=await auth_headers(planner))
    assert lot.json()["status"] == "canceled"
    running_body = await _order(client, running, planner)
    paused_body = await _order(client, paused, planner)
    assert (running_body["status"], running_body["interruptions"]) == ("canceled", [])
    assert paused_body["status"] == "canceled"
    [pause] = paused_body["interruptions"]
    assert pause["resumed_at"] is not None


async def test_the_parts_of_a_pool_order_stay_in_its_pool(
    db: AsyncSession, client, planner: User
) -> None:
    floor = await _floor(db, planner)
    pool_id = await floor.pool("Reconciled mills")
    order_id = await floor.order(5.0, 1, machine_id=None, machine_pool_id=pool_id)

    split = await _post(client, f"{ORDERS}/{order_id}/split", planner, {"quantities": [3.0, 2.0]})

    assert split.status_code == 200, split.text
    parts = split.json()
    assert [(p["quantity"], p["machine_id"], p["machine_pool_id"]) for p in parts] == [
        (3.0, None, pool_id),
        (2.0, None, pool_id),
    ]
    assert [p["queue_sequence"] for p in parts] == [1, 2]
    assert [p["status"] for p in parts] == ["queued", "queued"]


async def test_orders_of_different_pools_are_not_merged(
    db: AsyncSession, client, planner: User
) -> None:
    floor = await _floor(db, planner)
    first_pool = await floor.pool("Reconciled mills A")
    second_pool = await floor.pool("Reconciled mills B")
    first = await floor.order(5.0, 1, machine_id=None, machine_pool_id=first_pool)
    second = await floor.order(5.0, 1, machine_id=None, machine_pool_id=second_pool)

    versions = {i: (await _order(client, i, planner))["edit_version"] for i in (first, second)}
    merged = await _post(
        client,
        f"{ORDERS}/merge",
        planner,
        {"production_order_ids": [first, second], "expected_edit_versions": versions},
    )

    assert merged.status_code == 409, merged.text
    assert [(await _order(client, i, planner))["status"] for i in (first, second)] == [
        "queued",
        "queued",
    ]


async def test_an_ordinary_completion_cannot_reject_pieces(
    db: AsyncSession, client, planner: User
) -> None:
    floor = await _floor(db, planner)
    order_id = await floor.order(5.0, 1)
    await _post(client, f"{ORDERS}/{order_id}/start", planner)

    refused = await _post(
        client,
        f"{ORDERS}/{order_id}/completions",
        planner,
        {
            "quantity": 2.0,
            "quantity_accepted": 1.0,
            "quantity_rejected": 1.0,
            "completion_date": tenant_today().isoformat(),
        },
    )

    assert refused.status_code == 422, refused.text
    body = await _order(client, order_id, planner)
    assert (body["status"], body["quantity_completed"]) == ("in_progress", 0.0)


async def test_a_revived_order_takes_a_free_place_of_its_queue(
    db: AsyncSession, planner: User
) -> None:
    floor = await _floor(db, planner)
    live = await floor.order(5.0, 1)
    # Canceled without its intent, at the place a live order holds now.
    drifted = await floor.order(5.0, 1, status=ProductionOrderStatus.CANCELED)

    async with SessionLocal() as session:
        reconciler = LifecycleReconciler(sql_lifecycle_repositories(session), _Bus())
        reconciler.touch_production_orders([drifted])
        await reconciler.run(planner, datetime.now(UTC))
        await session.commit()

    async with SessionLocal() as check:
        revived = await check.get_one(ProductionOrderOrmModel, drifted)
        kept = await check.get_one(ProductionOrderOrmModel, live)
    assert (revived.status, revived.queue_sequence) == ("queued", 2)
    assert (kept.status, kept.queue_sequence) == ("queued", 1)


async def test_a_retried_completion_is_booked_once(db: AsyncSession, client, planner: User) -> None:
    floor = await _floor(db, planner)
    order_id = await floor.order(5.0, 1)
    started = await _post(client, f"{ORDERS}/{order_id}/start", planner)
    assert started.status_code == 200, started.text
    headers = {**await auth_headers(planner), "Idempotency-Key": "complete-1"}
    body = {"quantity": 2.0, "completion_date": tenant_today().isoformat()}

    first = await client.post(f"{ORDERS}/{order_id}/completions", json=body, headers=headers)
    retry = await client.post(f"{ORDERS}/{order_id}/completions", json=body, headers=headers)

    assert first.status_code == 200, first.text
    assert retry.status_code == 200, retry.text
    assert retry.json()["id"] == order_id
    assert retry.json()["quantity_completed"] == 2.0
    assert (await _order(client, order_id, planner))["quantity_completed"] == 2.0


async def test_a_completion_for_a_day_that_has_not_begun_is_refused(
    db: AsyncSession, client, planner: User
) -> None:
    floor = await _floor(db, planner)
    order_id = await floor.order(5.0, 1)
    started = await _post(client, f"{ORDERS}/{order_id}/start", planner)
    assert started.status_code == 200, started.text
    tomorrow = (tenant_today() + timedelta(days=1)).isoformat()

    response = await client.post(
        f"{ORDERS}/{order_id}/completions",
        json={"quantity": 2.0, "completion_date": tomorrow},
        headers=await auth_headers(planner),
    )

    assert response.status_code == 422, response.text
    assert response.json()["code"] == "CompletionDateInvalidError"
    assert (await _order(client, order_id, planner))["quantity_completed"] == 0.0


async def test_a_merge_checks_the_edit_version_of_every_order(
    db: AsyncSession, client, planner: User
) -> None:
    floor = await _floor(db, planner)
    first = await floor.order(5.0, 1)
    second = await floor.order(5.0, 2)
    read = {i: (await _order(client, i, planner))["edit_version"] for i in (first, second)}
    url = f"{ORDERS}/merge"
    ids = {"production_order_ids": [first, second]}

    without = await _post(client, url, planner, ids)
    partly = await _post(client, url, planner, {**ids, "expected_edit_versions": {first: 0}})
    stale = await _post(
        client, url, planner, {**ids, "expected_edit_versions": {first: 0, second: 5}}
    )
    merged = await _post(client, url, planner, {**ids, "expected_edit_versions": read})

    assert (without.status_code, partly.status_code) == (422, 422)
    assert stale.status_code == 409, stale.text
    assert stale.json()["code"] == "ConcurrentModificationError"
    assert merged.status_code == 200, merged.text
    assert merged.json()["quantity"] == 10.0
    assert merged.json()["edit_version"] == read[first] + 1
    assert (await _order(client, second, planner))["status"] == "canceled"
