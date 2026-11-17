"""
LifecycleReconciler on the SQL repositories and the throwaway SQLite file:
a seeded drift is written back with its changelog lines, timeline row and
events and a second run changes nothing; the reads see what another session
committed after this session first read a row, a production order's
interruptions included; every lifecycle lock runs and re-reads its rows; the
request factory builds a reconciler on the request's repositories.
"""

from collections.abc import Awaitable
from collections.abc import Callable

import httpx
import pytest
from fastapi import Depends
from fastapi import FastAPI
from sqlalchemy import select
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.catalogue.domain.events.made_item_events import MadeItemDemandItemStatusChanged
from src.modules.fulfillment.adapters.inbound.api.deps.lifecycle import get_lifecycle_lock_plan
from src.modules.fulfillment.adapters.inbound.api.deps.lifecycle import get_lifecycle_reconciler
from src.modules.fulfillment.adapters.outbound.persistence.lifecycle_store import (
    sql_lifecycle_repositories,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.bought_item_demand_item_model import (
    BoughtItemDemandItemOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.lot_event_model import (
    LotEventOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.lot_position_model import (
    LotPositionOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.made_item_demand_item_model import (
    MadeItemDemandItemOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.order_item_model import (
    OrderItemOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.order_model import OrderOrmModel
from src.modules.fulfillment.adapters.outbound.persistence.models.production_lot_model import (
    ProductionLotOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.production_order_interruption_model import (
    ProductionOrderInterruptionOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.production_order_model import (
    ProductionOrderOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.source_item_demand_item_model import (
    SourceItemDemandItemOrmModel,
)
from src.modules.fulfillment.application.services.lifecycle_drift import LifecycleDriftReport
from src.modules.fulfillment.application.services.lifecycle_loader import AggregateIds
from src.modules.fulfillment.application.services.lifecycle_loader import LifecycleLoader
from src.modules.fulfillment.application.services.lifecycle_lock_plan import LockPlan
from src.modules.fulfillment.application.services.lifecycle_reconciler import RECONCILED_AGGREGATES
from src.modules.fulfillment.application.services.lifecycle_reconciler import LifecycleReconciler
from src.modules.fulfillment.domain.events.lot_events import LotCompleted
from src.modules.fulfillment.domain.events.lot_events import LotPositionStatusChanged
from src.modules.fulfillment.domain.events.lot_events import LotStatusChanged
from src.modules.fulfillment.domain.events.order_events import OrderItemStatusChanged
from src.modules.fulfillment.domain.events.order_events import OrderStatusChanged
from src.modules.fulfillment.domain.value_objects.lifecycle_aggregate import LifecycleAggregate
from src.modules.platform.adapters.outbound.persistence.session import SessionLocal
from src.modules.platform.domain.entities.user import User
from tests.integration import _lifecycle_seed as seed

_A = LifecycleAggregate


class _Bus:
    def __init__(self) -> None:
        self.published: list[object] = []

    async def publish(self, event: object) -> None:
        self.published.append(event)


async def _seed_delivered_made_line(db: AsyncSession) -> dict[str, int]:
    """A lot whose only position's MADE line arrived in full, every stored
    status still saying ordered, with a made demand on the lot."""
    lot = await seed.lot(db, "planned")
    position = await seed.position(db, lot, "external", "ordered_or_queued")
    order = await seed.order(db, "ordered", ordered_date=seed.NOW)
    line = await seed.line(
        db, order, "ordered", at=position, ordered_date=seed.NOW, quantity_delivered=10.0
    )
    demand = await seed.made_demand(db, "ordered", lot, 10.0)
    await db.commit()
    return {
        "lot": lot.id,
        "position": position.id,
        "order": order.id,
        "line": line.id,
        "demand": demand.id,
    }


async def test_a_seeded_drift_is_written_back_with_changelog_timeline_and_events(
    db: AsyncSession, create_user: Callable[..., Awaitable[User]]
) -> None:
    actor = await create_user(username="planner", email="planner@example.com")
    ids = await _seed_delivered_made_line(db)
    bus = _Bus()

    async with SessionLocal() as session:
        reconciler = LifecycleReconciler(
            sql_lifecycle_repositories(session), bus, aggregates=set(LifecycleAggregate)
        )
        reconciler.touch_order_items([ids["line"]])
        result = await reconciler.run(actor, seed.NOW)
        await session.commit()

    assert {(c.aggregate, c.field.value) for c in result.changes} == {
        (_A.ORDER_ITEMS, "status"),
        (_A.LOT_POSITIONS, "status"),
        (_A.LOT_POSITIONS, "quantity_completed"),
        (_A.LOTS, "status"),
        (_A.LOTS, "completed_at"),
        (_A.ORDERS, "status"),
        (_A.ORDERS, "delivery_date"),
        (_A.MADE_DEMANDS, "status"),
    }
    async with SessionLocal() as check:
        lot = await check.get_one(ProductionLotOrmModel, ids["lot"])
        position = await check.get_one(LotPositionOrmModel, ids["position"])
        order = await check.get_one(OrderOrmModel, ids["order"])
        line = await check.get_one(OrderItemOrmModel, ids["line"])
        demand = await check.get_one(MadeItemDemandItemOrmModel, ids["demand"])
        events = (await check.scalars(select(LotEventOrmModel))).all()
    assert (lot.status, line.status, order.status, demand.status) == (
        "completed",
        "delivered",
        "delivered",
        "fulfilled",
    )
    assert (position.status, position.quantity_completed) == ("completed", 10.0)
    assert lot.completed_at is not None and order.delivery_date is not None
    assert lot.changes[-2].endswith("Status: planned → completed (derived from recorded facts).")
    assert f", {actor.full_name}, " in lot.changes[-1]
    assert [(e.lot_id, e.event_type, e.actor_id) for e in events] == [
        (ids["lot"], "lot_completed", actor.id)
    ]
    assert [type(e) for e in bus.published] == [
        OrderItemStatusChanged,
        LotPositionStatusChanged,
        LotStatusChanged,
        LotCompleted,
        OrderStatusChanged,
        MadeItemDemandItemStatusChanged,
    ]

    async with SessionLocal() as again:
        reconciler = LifecycleReconciler(
            sql_lifecycle_repositories(again), _Bus(), aggregates=set(LifecycleAggregate)
        )
        reconciler.touch_order_items([ids["line"]])
        assert (await reconciler.run(actor, seed.NOW)).changes == ()
        report = await LifecycleDriftReport(sql_lifecycle_repositories(again)).run()
    assert report.rows == []


async def test_the_reads_see_what_another_session_committed_after_the_first_read(
    db: AsyncSession, create_user: Callable[..., Awaitable[User]], allow_lifecycle_drift: None
) -> None:
    actor = await create_user()
    order = await seed.order(db, "ordered", ordered_date=seed.NOW)
    touched = await seed.line(db, order, "ordered", ordered_date=seed.NOW)
    sibling = await seed.line(db, order, "ordered", ordered_date=seed.NOW)
    await db.commit()

    async with SessionLocal() as request:
        # The request read the sibling line before reconciling and still holds
        # the row. The sibling is no target, so no lock re-reads it, and its
        # stored status stays behind the delivery the other session recorded.
        held = await request.get_one(OrderItemOrmModel, sibling.id)
        async with SessionLocal() as other:
            await other.execute(
                update(OrderItemOrmModel)
                .where(OrderItemOrmModel.id == sibling.id)
                .values(quantity_delivered=10.0)
            )
            await other.commit()
        reconciler = LifecycleReconciler(
            sql_lifecycle_repositories(request), _Bus(), aggregates={_A.ORDER_ITEMS, _A.ORDERS}
        )
        reconciler.touch_order_items([touched.id])
        result = await reconciler.run(actor, seed.NOW)
        await request.commit()

    assert held.quantity_delivered == 10.0
    assert [(c.aggregate, c.id, c.new) for c in result.changes if c.field.value == "status"] == [
        (_A.ORDERS, order.id, "partially_delivered")
    ]


@pytest.mark.parametrize("read", ["get_by_ids", "get_by_lot_position_ids"])
async def test_a_refreshed_production_order_read_sees_an_interruption_resumed_meanwhile(
    db: AsyncSession, read: str
) -> None:
    lot = await seed.lot(db, "in_progress")
    position = await seed.position(db, lot, "internal", "in_progress")
    production_order = await seed.production_order(db, position, "paused", actual_start=seed.NOW)
    interruption = await seed.add(
        db,
        ProductionOrderInterruptionOrmModel(
            created=seed.NOW,
            production_order_id=production_order.id,
            paused_at=seed.NOW,
            paused_by_id=1,
        ),
    )
    await db.commit()
    key = production_order.id if read == "get_by_ids" else position.id

    async with SessionLocal() as request:
        # The request read the open interruption earlier and still holds the
        # row when another session resumes the order.
        held = await request.get_one(ProductionOrderInterruptionOrmModel, interruption.id)
        async with SessionLocal() as other:
            await other.execute(
                update(ProductionOrderInterruptionOrmModel)
                .where(ProductionOrderInterruptionOrmModel.id == interruption.id)
                .values(resumed_at=seed.NOW, resumed_by_id=1)
            )
            await other.execute(
                update(ProductionOrderOrmModel)
                .where(ProductionOrderOrmModel.id == production_order.id)
                .values(status="in_progress")
            )
            await other.commit()
        repository = sql_lifecycle_repositories(request).production_orders
        stale = await getattr(repository, read)([key])
        fresh = await getattr(repository, read)([key], refresh=True)

    assert [i.resumed_by_id for i in stale[0].interruptions] == [None]
    assert [i.resumed_by_id for i in fresh[0].interruptions] == [1]
    assert held.resumed_by_id == 1


async def test_every_lifecycle_lock_runs_and_re_reads_its_rows(db: AsyncSession) -> None:
    lot = await seed.lot(db, "planned")
    position = await seed.position(db, lot, "internal", "ordered_or_queued")
    production_order = await seed.production_order(db, position, "queued")
    order = await seed.order(db, "draft")
    line = await seed.line(db, order, "pending")
    bought = await seed.bought_demand(db, "open", None, 1.0)
    made = await seed.made_demand(db, "open", None, 1.0)
    source = await seed.source_demand(db, "open")
    await db.commit()
    rows = [
        (ProductionLotOrmModel, lot.id, "lots"),
        (ProductionOrderOrmModel, production_order.id, "production_orders"),
        (OrderOrmModel, order.id, "orders"),
        (OrderItemOrmModel, line.id, "order_items"),
        (BoughtItemDemandItemOrmModel, bought.id, "bought_demands"),
        (MadeItemDemandItemOrmModel, made.id, "made_demands"),
        (SourceItemDemandItemOrmModel, source.id, "source_demands"),
    ]

    async with SessionLocal() as request:
        repositories = sql_lifecycle_repositories(request)
        held = [await request.get_one(model, row_id) for model, row_id, _ in rows]
        async with SessionLocal() as other:
            for model, row_id, _ in rows:
                await other.execute(update(model).where(model.id == row_id).values(note="fresh"))
            await other.commit()
        for _, row_id, repository in rows:
            await getattr(repositories, repository).lock_for_update([row_id])

    assert [row.note for row in held] == ["fresh"] * len(rows)


async def test_the_request_factory_builds_a_reconciler_on_the_requests_lock_plan(
    db: AsyncSession,
) -> None:
    repositories = sql_lifecycle_repositories(db)
    plan = get_lifecycle_lock_plan(repositories)

    reconciler = get_lifecycle_reconciler(repositories=repositories, lock_plan=plan, bus=_Bus())

    assert isinstance(reconciler, LifecycleReconciler)
    assert reconciler.aggregates == RECONCILED_AGGREGATES
    assert reconciler.lock_plan is plan


async def test_one_request_shares_one_lock_plan_and_the_next_gets_its_own() -> None:
    app = FastAPI()
    plans: list[LockPlan] = []

    @app.get("/probe")
    async def probe(
        plan: LockPlan = Depends(get_lifecycle_lock_plan),
        reconciler: LifecycleReconciler = Depends(get_lifecycle_reconciler),
    ) -> dict[str, bool]:
        plans.append(plan)
        return {"shared": reconciler.lock_plan is plan}

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        first = (await client.get("/probe")).json()
        second = (await client.get("/probe")).json()

    assert first == second == {"shared": True}
    assert plans[0] is not plans[1]


async def test_a_line_finds_the_bought_and_source_demands_allocated_to_it(
    db: AsyncSession,
) -> None:
    order = await seed.order(db, "ordered", ordered_date=seed.NOW)
    other = await seed.line(db, order, "ordered", ordered_date=seed.NOW)
    touched = await seed.line(db, order, "ordered", ordered_date=seed.NOW)
    # Demand ids are chosen so a read keyed on the wrong column would find the
    # decoys: each decoy's id equals the touched line's id, but its allocation
    # sits on the other line.
    bought_decoy = await seed.bought_demand(db, "ordered", other, 2.0, id=touched.id)
    bought = await seed.bought_demand(db, "ordered", touched, 3.0, id=touched.id + 100)
    source_decoy = await seed.source_demand(db, "ordered", id=touched.id, lot_id=1)
    source = await seed.source_demand(db, "ordered", id=touched.id + 100, lot_id=2)
    await seed.source_allocation(db, source_decoy, other, 4.0)
    await seed.source_allocation(db, source, touched, 5.0)
    await db.commit()
    repositories = sql_lifecycle_repositories(db)

    bought_rows = await repositories.bought_allocations.get_by_order_item_ids([touched.id])
    source_rows = await repositories.source_allocations.get_by_order_item_ids([touched.id])
    both = await repositories.bought_allocations.get_by_order_item_ids([touched.id, other.id])
    targets = await LifecycleLoader(repositories, refresh=True).widen(
        AggregateIds.of({_A.ORDER_ITEMS: [touched.id]})
    )

    assert [(a.demand_item_id, a.order_item_id, a.quantity) for a in bought_rows] == [
        (bought.id, touched.id, 3.0)
    ]
    assert [(a.demand_item_id, a.order_item_id, a.quantity) for a in source_rows] == [
        (source.id, touched.id, 5.0)
    ]
    assert {a.demand_item_id for a in both} == {bought.id, bought_decoy.id}
    assert targets.get(_A.BOUGHT_DEMANDS) == {bought.id}
    assert targets.get(_A.SOURCE_DEMANDS) == {source.id}
