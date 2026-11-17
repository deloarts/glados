"""
Scenarios over a lot of several positions and an order of several lines,
driven over HTTP on the throwaway SQLite file. After every request the
stored status of every aggregate the scenario touches (the lot, each
position with its kind, each production order, the supplier order, each
line and the demands) is read from the database and compared with the
expected table as a whole, and the drift check after the test confirms that
every stored status equals its derivation. The project of the scenario
cannot be deleted while its work is live and can once all of it ended.
"""

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.fulfillment.adapters.outbound.persistence.models.bought_item_demand_item_model import (
    BoughtItemDemandItemOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.lot_position_model import (
    LotPositionOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.order_item_model import (
    OrderItemOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.order_model import OrderOrmModel
from src.modules.fulfillment.adapters.outbound.persistence.models.production_lot_model import (
    ProductionLotOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.production_order_model import (
    ProductionOrderOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.order_repository.order import (
    SqlAlchemyOrderRepository,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.production_lot_repository.lot import (
    SqlAlchemyProductionLotRepository,
)
from src.modules.fulfillment.domain.entities.lot_position import LotPosition
from src.modules.fulfillment.domain.entities.order import Order
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionKind
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionStatus
from src.modules.fulfillment.domain.value_objects.order_status import OrderStatus
from src.modules.platform.domain.value_objects.permission import Permission
from tests.integration._edit_versions import line_version
from tests.integration._edit_versions import lot_version
from tests.integration._edit_versions import production_order_version
from tests.integration._edit_versions import row_version
from tests.integration._tenant_day import tenant_today
from tests.integration.repository_reads._graph import Graph
from tests.integration.repository_reads._graph import make
from tests.integration.test_api_production_order_reconciled import ORDERS
from tests.integration.test_api_production_order_reconciled import _Floor
from tests.integration.test_api_production_order_reconciled import _seed_production_settings  # noqa: F401

WEB = "/api/v1/web"
LOTS = f"{WEB}/production-lots"
SUPPLIER_ORDERS = f"{WEB}/orders"
DELIVER_URL = f"{WEB}/bought-items-allocations/order-item"

PERMISSIONS = [
    Permission.WRITE_LOTS,
    Permission.MANAGE_LOTS,
    Permission.WRITE_PRODUCTION_ORDERS,
    Permission.MANAGE_PRODUCTION_ORDERS,
    Permission.WRITE_ORDERS,
    Permission.MANAGE_ORDERS,
    Permission.RECEIVE_DELIVERIES,
    Permission.WRITE_ALLOCATIONS,
    Permission.WRITE_DEMAND_ITEMS,
    Permission.MANAGE_DEMAND_ITEMS,
    Permission.MANAGE_PROJECTS,
]


class Shop:
    """The floor's lot with extra positions, one supplier order and the
    client that drives them, with the expected status table."""

    def __init__(
        self, db: AsyncSession, client: Any, floor: _Floor, graph: Graph, order_id: int
    ) -> None:
        self.db = db
        self.client = client
        self.floor = floor
        self.graph = graph
        self.order_id = order_id
        self.expected: dict[str, str] = {}

    @classmethod
    async def open(cls, db: AsyncSession, auth_client: Any, extra_positions: int) -> "Shop":
        client = await auth_client(
            permissions=PERMISSIONS, username="scenario", email="scenario@example.com"
        )
        me = (await client.get(f"{WEB}/users/me")).json()
        floor = await _Floor(db, me["id"]).build()
        repo = SqlAlchemyProductionLotRepository(db)
        for sequence in range(2, 2 + extra_positions):
            await repo.save_position(
                make(
                    LotPosition,
                    sequence=sequence,
                    kind=LotPositionKind.UNASSIGNED,
                    status=LotPositionStatus.PENDING,
                    quantity=10.0,
                    quantity_completed=0.0,
                    creator_id=floor.creator_id,
                    lot_id=floor.lot_id,
                )
            )
        await db.commit()
        graph = await Graph.seed(db)
        supplier = await graph.supplier()
        order = await SqlAlchemyOrderRepository(db).save(
            make(
                Order,
                order_number=f"O-SCN-{floor.lot_id}",
                status=OrderStatus.DRAFT,
                creator_id=floor.creator_id,
                supplier_id=supplier.id,
            )
        )
        await db.commit()
        return cls(db, client, floor, graph, order.id)

    async def positions(self) -> list[int]:
        rows = await self.db.execute(
            select(LotPositionOrmModel.id)
            .where(LotPositionOrmModel.lot_id == self.floor.lot_id)
            .order_by(LotPositionOrmModel.sequence)
        )
        return list(rows.scalars())

    async def table(self) -> dict[str, str]:
        """The stored status of the lot, its positions and production
        orders, the supplier order, its lines and the project's demands."""
        self.db.expire_all()
        found: dict[str, str] = {}
        lot = await self.db.get(ProductionLotOrmModel, self.floor.lot_id)
        assert lot is not None
        found["lot"] = lot.status
        positions = (
            await self.db.execute(
                select(LotPositionOrmModel)
                .where(LotPositionOrmModel.lot_id == self.floor.lot_id)
                .order_by(LotPositionOrmModel.sequence)
            )
        ).scalars()
        position_ids = []
        for p in positions:
            found[f"position{p.sequence}"] = f"{p.status}/{p.kind}"
            position_ids.append(p.id)
        orders = (
            await self.db.execute(
                select(ProductionOrderOrmModel).where(
                    ProductionOrderOrmModel.lot_position_id.in_(position_ids)
                )
            )
        ).scalars()
        for o in orders:
            found[f"production_order{o.id}"] = o.status
        order = await self.db.get(OrderOrmModel, self.order_id)
        assert order is not None
        found["order"] = order.status
        lines = (
            await self.db.execute(
                select(OrderItemOrmModel).where(OrderItemOrmModel.order_id == self.order_id)
            )
        ).scalars()
        for line in lines:
            found[f"line{line.id}"] = line.status
        demands = (
            await self.db.execute(
                select(BoughtItemDemandItemOrmModel).where(
                    BoughtItemDemandItemOrmModel.project_id == self.floor.project_id
                )
            )
        ).scalars()
        for d in demands:
            found[f"bought_demand{d.id}"] = d.status
        return found

    async def step(self, response: Any, **changes: str) -> Any:
        """Asserts the request went through and every aggregate now reads
        its expected status: the previous table with `changes` applied."""
        assert response.status_code in (200, 201), response.text
        self.expected.update(changes)
        assert await self.table() == self.expected
        return response

    # ── Requests ─────────────────────────────────────────────────────

    async def assign_external(self, position_id: int) -> Any:
        return await self.client.post(
            f"{LOTS}/{self.floor.lot_id}/positions/{position_id}/assign",
            json={"order_id": self.order_id, "unit": "pcs"},
        )

    async def made_line(self, position_id: int) -> int:
        rows = await self.db.execute(
            select(OrderItemOrmModel.id).where(
                OrderItemOrmModel.lot_position_id == position_id,
                OrderItemOrmModel.canceled_at.is_(None),
            )
        )
        return int(rows.scalar_one())

    async def production_order(self, position_id: int, quantity: float, sequence: int) -> int:
        own, self.floor.position_id = self.floor.position_id, position_id
        try:
            return await self.floor.order(quantity, sequence)
        finally:
            self.floor.position_id = own

    async def run(self, order_id: int, quantity: float) -> tuple[Any, Any]:
        started = await self.client.post(f"{ORDERS}/{order_id}/start", json={})
        assert started.status_code == 200, started.text
        done = await self.client.post(
            f"{ORDERS}/{order_id}/completions",
            json={"quantity": quantity, "completion_date": tenant_today().isoformat()},
        )
        return started, done

    async def deliver(self, line_id: int, quantity: float) -> Any:
        return await self.client.put(
            f"{DELIVER_URL}/{line_id}/deliver", params={"quantity": quantity}
        )

    async def delete_project(self) -> Any:
        url = f"{WEB}/projects/{self.floor.project_id}"
        version = await row_version(self.client, url)
        return await self.client.delete(url, params={"expected_edit_version": version})


async def test_a_held_lot_completes_when_its_last_made_line_arrives(
    db: AsyncSession, auth_client: Any
) -> None:
    shop = await Shop.open(db, auth_client, extra_positions=1)
    first, second = await shop.positions()
    po = await shop.production_order(first, 10.0, 1)

    assigned = await shop.assign_external(second)
    assert assigned.status_code == 200, assigned.text
    line = await shop.made_line(second)
    shop.expected = {
        "lot": "partially_planned",
        "position1": "ordered_or_queued/internal",
        "position2": "pending/external",
        f"production_order{po}": "queued",
        "order": "draft",
        f"line{line}": "pending",
    }
    assert await shop.table() == shop.expected

    blocked = await shop.delete_project()
    assert blocked.status_code == 409, blocked.text
    assert "1 lot, 1 production order, 1 order line" in blocked.json()["detail"]

    await shop.step(
        await shop.client.put(f"{SUPPLIER_ORDERS}/{shop.order_id}/submit", json={}),
        lot="planned",
        position2="ordered_or_queued/external",
        order="ordered",
        **{f"line{line}": "ordered"},
    )
    _started, done = await shop.run(po, 10.0)
    await shop.step(
        done,
        lot="in_progress",
        position1="completed/internal",
        **{f"production_order{po}": "completed"},
    )
    await shop.step(
        await shop.client.post(f"{LOTS}/{shop.floor.lot_id}/hold", json={"reason": "Check"}),
        lot="on_hold",
    )
    await shop.step(
        await shop.deliver(line, 10.0),
        lot="completed",
        position2="completed/external",
        order="delivered",
        **{f"line{line}": "delivered"},
    )

    deleted = await shop.delete_project()
    assert deleted.status_code == 200, deleted.text


async def test_an_order_of_a_bought_a_canceled_and_a_made_line_is_delivered(
    db: AsyncSession, auth_client: Any
) -> None:
    shop = await Shop.open(db, auth_client, extra_positions=1)
    first, second = await shop.positions()
    po = await shop.production_order(first, 10.0, 1)
    item = await shop.graph.bought_item()
    supplier_id = (await db.get(OrderOrmModel, shop.order_id)).supplier_id  # type: ignore[union-attr]

    bought = []
    for quantity in (4.0, 2.0):
        added = await shop.client.post(
            f"{SUPPLIER_ORDERS}/{shop.order_id}/items",
            json={
                "bought_item_id": item.id,
                "order_id": shop.order_id,
                "supplier_id": supplier_id,
                "project_id": shop.floor.project_id,
                "quantity": quantity,
                "unit": "M",
            },
        )
        assert added.status_code in (200, 201), added.text
        bought.append(added.json()["id"])
    kept, dropped = bought
    demand = await shop.client.post(
        f"{WEB}/bought-items-demands/",
        json={
            "item_id": item.id,
            "project_id": shop.floor.project_id,
            "quantity": 4.0,
            "unit": "M",
        },
    )
    assert demand.status_code in (200, 201), demand.text
    demand_id = demand.json()["id"]
    assigned = await shop.assign_external(second)
    assert assigned.status_code == 200, assigned.text
    line = await shop.made_line(second)
    shop.expected = {
        "lot": "partially_planned",
        "position1": "ordered_or_queued/internal",
        "position2": "pending/external",
        f"production_order{po}": "queued",
        "order": "draft",
        f"line{kept}": "pending",
        f"line{dropped}": "pending",
        f"line{line}": "pending",
        f"bought_demand{demand_id}": "open",
    }
    assert await shop.table() == shop.expected

    await shop.step(
        await shop.client.post(
            f"{WEB}/bought-items-allocations/",
            json={"demand_item_id": demand_id, "order_item_id": kept, "quantity": 4.0},
        ),
        **{f"bought_demand{demand_id}": "allocated"},
    )
    await shop.step(
        await shop.client.put(f"{SUPPLIER_ORDERS}/{shop.order_id}/submit", json={}),
        lot="planned",
        position2="ordered_or_queued/external",
        order="ordered",
        **{
            f"line{kept}": "ordered",
            f"line{dropped}": "ordered",
            f"line{line}": "ordered",
            f"bought_demand{demand_id}": "ordered",
        },
    )
    await shop.step(
        await shop.deliver(kept, 1.3),
        order="partially_delivered",
        **{f"line{kept}": "partially_delivered"},
    )
    await shop.step(
        await shop.deliver(kept, 2.7),
        **{f"line{kept}": "delivered", f"bought_demand{demand_id}": "fulfilled"},
    )
    await shop.step(
        await shop.client.post(
            f"{SUPPLIER_ORDERS}/{shop.order_id}/items/{dropped}/cancel",
            params={
                "expected_edit_version": await line_version(shop.client, shop.order_id, dropped)
            },
        ),
        **{f"line{dropped}": "canceled"},
    )
    _started, done = await shop.run(po, 10.0)
    await shop.step(
        done,
        lot="in_progress",
        position1="completed/internal",
        **{f"production_order{po}": "completed"},
    )
    await shop.step(
        await shop.deliver(line, 10.0),
        lot="completed",
        position2="completed/external",
        order="delivered",
        **{f"line{line}": "delivered"},
    )


async def test_a_scrap_after_a_made_step_shrinks_the_later_positions_and_the_lot_completes(
    db: AsyncSession, auth_client: Any
) -> None:
    shop = await Shop.open(db, auth_client, extra_positions=2)
    first, second, third = await shop.positions()
    # The floor's own position comes first and is bought in; the second and
    # third run internally.
    assigned = await shop.assign_external(first)
    assert assigned.status_code == 200, assigned.text
    line = await shop.made_line(first)
    middle = await shop.production_order(second, 10.0, 1)
    last = await shop.production_order(third, 10.0, 2)
    submitted = await shop.client.put(f"{SUPPLIER_ORDERS}/{shop.order_id}/submit", json={})
    assert submitted.status_code == 200, submitted.text
    shop.expected = {
        "lot": "planned",
        "position1": "ordered_or_queued/external",
        "position2": "ordered_or_queued/internal",
        "position3": "ordered_or_queued/internal",
        f"production_order{middle}": "queued",
        f"production_order{last}": "queued",
        "order": "ordered",
        f"line{line}": "ordered",
    }
    assert await shop.table() == shop.expected

    await shop.step(
        await shop.deliver(line, 10.0),
        lot="in_progress",
        position1="completed/external",
        order="delivered",
        **{f"line{line}": "delivered"},
    )
    started = await shop.client.post(f"{ORDERS}/{middle}/start", json={})
    await shop.step(
        started,
        position2="in_progress/internal",
        **{f"production_order{middle}": "in_progress"},
    )
    await shop.step(
        await shop.client.post(
            f"{ORDERS}/{middle}/completions",
            json={"quantity": 4.0, "completion_date": tenant_today().isoformat()},
        ),
        position2="partially_completed/internal",
    )
    await shop.step(
        await shop.client.post(
            f"{ORDERS}/{middle}/scrap",
            json={
                "quantity": 2.0,
                "reason": "tool_breakage",
                "create_replacement": False,
                "expected_edit_version": await production_order_version(shop.client, middle),
                "expected_lot_edit_version": await lot_version(shop.client, shop.floor.lot_id),
            },
        )
    )
    lot = await shop.client.get(f"{LOTS}/{shop.floor.lot_id}")
    assert lot.json()["quantity"] == 8.0
    assert [p["quantity"] for p in lot.json()["positions"]] == [10.0, 8.0, 8.0]

    await shop.step(
        await shop.client.post(
            f"{ORDERS}/{middle}/completions",
            json={"quantity": 4.0, "completion_date": tenant_today().isoformat()},
        ),
        position2="completed/internal",
        **{f"production_order{middle}": "completed"},
    )
    _started, done = await shop.run(last, 8.0)
    await shop.step(
        done,
        lot="completed",
        position3="completed/internal",
        **{f"production_order{last}": "completed"},
    )


async def test_deliver_all_on_a_partially_ordered_order_judges_each_line_and_books_nothing(
    db: AsyncSession, auth_client: Any
) -> None:
    """One of two MADE lines is marked ordered on its own, so the order is
    partially ordered. Deliver-all judges each line as a single delivery would: the
    ordered line's position has no pieces from its predecessor yet, so the
    request is refused as that delivery would be, and nothing is booked."""
    shop = await Shop.open(db, auth_client, extra_positions=2)
    _first, second, third = await shop.positions()
    for position_id in (second, third):
        assigned = await shop.assign_external(position_id)
        assert assigned.status_code == 200, assigned.text
    line = await shop.made_line(second)
    marked = await shop.client.put(
        f"{SUPPLIER_ORDERS}/{shop.order_id}/items/{line}/mark-ordered", json={}
    )
    assert marked.status_code == 200, marked.text
    shop.expected = await shop.table()
    assert (shop.expected["order"], shop.expected[f"line{line}"]) == (
        "partially_ordered",
        "ordered",
    )

    refused = await shop.client.put(f"{SUPPLIER_ORDERS}/{shop.order_id}/deliver-all-items", json={})

    assert refused.status_code == 422, refused.text
    assert refused.json()["code"] == "LotPositionOverflowError"
    assert await shop.table() == shop.expected
    db.expire_all()
    stored = await db.get(OrderItemOrmModel, line)
    assert stored is not None and stored.quantity_delivered == 0.0
