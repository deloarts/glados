"""
Writers on an order line or a lot whose demand is allocated on a second line
or lot as well, where a demand with a lower id sits on that second line or
lot only. A writer that touches the shared demand once it has written its
facts makes the run widen the demand to that neighbour, which sorts before
the demand in the lock order, so the lock step of every writer locks it up
front (LifecycleReconciler.lock_touched) instead of the run refusing it with
LockOrderError, a 500. Bought and source demands share two lines of two
orders, made demands two lots, and a source line carries the raw material of
two lots. The rows are seeded and their statuses then derived, so the drift
check after each test covers the neighbour too.
"""

from dataclasses import dataclass
from typing import Any

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.catalogue.adapters.outbound.persistence.models.admin_settings_model.orders import (
    AdminOrderSettingsOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.bought_item_allocation_model import (
    BoughtItemAllocationOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.bought_item_demand_item_model import (
    BoughtItemDemandItemOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.made_item_allocation_model import (
    MadeItemAllocationOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.order_item_delivery_model import (
    OrderItemDeliveryOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.order_item_model import (
    OrderItemOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.production_lot_model import (
    ProductionLotOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.source_item_allocation_model import (
    SourceItemAllocationOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.source_item_demand_item_model import (
    SourceItemDemandItemOrmModel,
)
from src.modules.platform.domain.value_objects.permission import Permission
from tests.integration import _lifecycle_seed as seed
from tests.integration._edit_versions import line_version
from tests.integration._edit_versions import lot_version
from tests.integration._edit_versions import order_version
from tests.integration._edit_versions import production_order_version
from tests.integration.repository_reads._graph import Graph
from tests.integration.test_api_scrap_pieces import _seed_lot_and_order
from tests.integration.test_api_scrap_pieces import _seed_production_settings  # noqa: F401

WEB = "/api/v1/web"
ORDERS = f"{WEB}/orders"
LOTS = f"{WEB}/production-lots"
PRODUCTION_ORDERS = f"{WEB}/production-orders"
DELIVER = f"{WEB}/bought-items-allocations/order-item"

FAMILIES = ["bought", "source"]

_PERMISSIONS = [
    Permission.WRITE_ORDERS,
    Permission.MANAGE_ORDERS,
    Permission.RECEIVE_DELIVERIES,
    Permission.WRITE_LOTS,
    Permission.MANAGE_LOTS,
    Permission.WRITE_PRODUCTION_ORDERS,
    Permission.MANAGE_PRODUCTION_ORDERS,
    Permission.WRITE_ALLOCATIONS,
]


@pytest.fixture
async def manager(auth_client: Any) -> httpx.AsyncClient:
    client: httpx.AsyncClient = await auth_client(permissions=_PERMISSIONS)
    return client


@dataclass
class _Lines:
    """Two lines of 10 on two orders. The demand `shared` has 5 on each
    line, `neighbour`, with the lower id, has 5 on the second line only."""

    first_order: int
    first: int
    second: int
    neighbour: int
    shared: int


async def _shared_lines(
    db: AsyncSession,
    family: str,
    *,
    order_status: str = "ordered",
    line_status: str = "ordered",
    delivered: float = 0.0,
    allocated: float = 5.0,
) -> _Lines:
    """`_Lines` of bought or source lines, the first one with `delivered`
    pieces booked and `allocated` pieces of the shared demand."""
    ordered = {} if line_status == "pending" else {"ordered_date": seed.NOW}
    first_order = await seed.order(db, order_status, **ordered)
    second_order = await seed.order(db, "ordered", ordered_date=seed.NOW)
    first = await seed.line(db, first_order, line_status, quantity_delivered=delivered, **ordered)
    second = await seed.line(db, second_order, "ordered", ordered_date=seed.NOW)
    if family == "bought":
        neighbour_id, shared_id = await _bought_demands(db, first, second, allocated)
    else:
        for line in (first, second):
            line.line_type = "SOURCE"
            line.bought_item_id = None
            line.source_item_id = 1
        neighbour_id, shared_id = await _source_demands(db, first, second, allocated)
    await db.commit()
    await seed.settle(db)
    return _Lines(first_order.id, first.id, second.id, neighbour_id, shared_id)


async def _bought_demands(
    db: AsyncSession, first: OrderItemOrmModel, second: OrderItemOrmModel, allocated: float
) -> tuple[int, int]:
    neighbour = await seed.bought_demand(db, "open", second, 5.0)
    shared = await seed.bought_demand(db, "open", first, 5.0 + allocated)
    rows = await db.scalars(
        select(BoughtItemAllocationOrmModel).where(
            BoughtItemAllocationOrmModel.demand_item_id == shared.id
        )
    )
    for row in rows:
        row.quantity = allocated
    await seed.add(
        db,
        BoughtItemAllocationOrmModel(
            demand_item_id=shared.id, order_item_id=second.id, source="order", quantity=5.0
        ),
    )
    return neighbour.id, shared.id


async def _source_demands(
    db: AsyncSession, first: OrderItemOrmModel, second: OrderItemOrmModel, allocated: float
) -> tuple[int, int]:
    """Source demands of two draft lots, each the lot's raw material."""
    lots = [await seed.lot(db, "draft"), await seed.lot(db, "draft")]
    neighbour = await seed.source_demand(db, "open", lot_id=lots[0].id, quantity=5.0)
    shared = await seed.source_demand(db, "open", lot_id=lots[1].id, quantity=5.0 + allocated)
    lots[0].input_demand_id = neighbour.id
    lots[1].input_demand_id = shared.id
    await seed.source_allocation(db, neighbour, second, 5.0)
    await seed.source_allocation(db, shared, first, allocated)
    await seed.source_allocation(db, shared, second, 5.0)
    return neighbour.id, shared.id


async def _assert_neighbour_is_derived(db: AsyncSession, lines: _Lines, family: str) -> None:
    """The neighbour still holds its 5 pieces on the second line."""
    model = BoughtItemAllocationOrmModel if family == "bought" else SourceItemAllocationOrmModel
    allocation = await db.scalar(
        select(model)
        .where(model.demand_item_id == lines.neighbour)
        .execution_options(populate_existing=True)
    )
    assert allocation is not None
    assert allocation.quantity == 5.0


# ── Order lines ──────────────────────────────────────────────────────────


@pytest.mark.parametrize("family", FAMILIES)
async def test_shared_demand_lock_cancel_a_line(
    db: AsyncSession, manager: httpx.AsyncClient, family: str
) -> None:
    lines = await _shared_lines(db, family)
    version = await line_version(manager, lines.first_order, lines.first)

    canceled = await manager.post(
        f"{ORDERS}/{lines.first_order}/items/{lines.first}/cancel",
        params={"expected_edit_version": version},
    )

    assert canceled.status_code == 200, canceled.text
    assert canceled.json()["status"] == "canceled"
    await _assert_neighbour_is_derived(db, lines, family)


@pytest.mark.parametrize("family", FAMILIES)
async def test_shared_demand_lock_close_a_line_short(
    db: AsyncSession, manager: httpx.AsyncClient, family: str
) -> None:
    lines = await _shared_lines(db, family, line_status="partially_delivered", delivered=2.0)
    version = await line_version(manager, lines.first_order, lines.first)

    closed = await manager.post(
        f"{ORDERS}/{lines.first_order}/items/{lines.first}/close-short",
        params={"expected_edit_version": version},
    )

    assert closed.status_code == 200, closed.text
    assert closed.json()["status"] == "delivered"
    await _assert_neighbour_is_derived(db, lines, family)


@pytest.mark.parametrize("family", FAMILIES)
async def test_shared_demand_lock_remove_a_pending_line(
    db: AsyncSession, manager: httpx.AsyncClient, family: str
) -> None:
    lines = await _shared_lines(db, family, order_status="draft", line_status="pending")

    removed = await manager.delete(
        f"{ORDERS}/{lines.first_order}/items/{lines.first}",
        params={
            "expected_edit_version": await line_version(manager, lines.first_order, lines.first)
        },
    )

    assert removed.status_code == 204, removed.text
    await _assert_neighbour_is_derived(db, lines, family)


@pytest.mark.parametrize("family", FAMILIES)
async def test_shared_demand_lock_cancel_an_order(
    db: AsyncSession, manager: httpx.AsyncClient, family: str
) -> None:
    lines = await _shared_lines(db, family)
    version = await order_version(manager, lines.first_order)

    canceled = await manager.put(
        f"{ORDERS}/{lines.first_order}/cancel", params={"expected_edit_version": version}
    )

    assert canceled.status_code == 200, canceled.text
    assert canceled.json()["status"] == "canceled"
    await _assert_neighbour_is_derived(db, lines, family)


@pytest.mark.parametrize("family", FAMILIES)
async def test_shared_demand_lock_reject_pieces_as_lost(
    db: AsyncSession, manager: httpx.AsyncClient, family: str
) -> None:
    lines = await _shared_lines(db, family, allocated=10.0)

    booked = await manager.put(
        f"{DELIVER}/{lines.first}/deliver",
        params={"quantity": 2.0},
        json={
            "quantity_rejected": 3.0,
            "rejection_reason": "transport_damage",
            "rejection_outcome": "lost",
        },
    )

    assert booked.status_code == 200, booked.text
    assert booked.json()["quantity_rejected_lost"] == 3.0
    await _assert_neighbour_is_derived(db, lines, family)


@pytest.mark.parametrize("family", FAMILIES)
async def test_shared_demand_lock_close_short_within_the_under_tolerance(
    db: AsyncSession, manager: httpx.AsyncClient, family: str
) -> None:
    settings = await db.get(AdminOrderSettingsOrmModel, 1)
    assert settings is not None
    settings.under_delivery_tolerance_percent = 10.0
    lines = await _shared_lines(db, family, allocated=10.0)

    booked = await manager.put(f"{DELIVER}/{lines.first}/deliver", params={"quantity": 9.0})

    assert booked.status_code == 200, booked.text
    assert (booked.json()["status"], booked.json()["closed_short_from"]) == ("delivered", 10)
    await _assert_neighbour_is_derived(db, lines, family)


@pytest.mark.parametrize("family", FAMILIES)
async def test_shared_demand_lock_correct_a_delivery_beyond_the_quantity(
    db: AsyncSession, manager: httpx.AsyncClient, family: str
) -> None:
    settings = await db.get(AdminOrderSettingsOrmModel, 1)
    assert settings is not None
    settings.over_delivery_tolerance_percent = 10.0
    lines = await _shared_lines(db, family, line_status="delivered", delivered=11.0, allocated=11.0)
    delivery = await db.scalar(
        select(OrderItemDeliveryOrmModel.id).where(
            OrderItemDeliveryOrmModel.order_item_id == lines.first
        )
    )
    version = await line_version(manager, lines.first_order, lines.first)

    corrected = await manager.post(
        f"{ORDERS}/{lines.first_order}/items/{lines.first}/deliveries/{delivery}/correct",
        json={"quantity": 2.0, "reason": "counted twice", "expected_edit_version": version},
    )

    assert corrected.status_code == 200, corrected.text
    assert corrected.json()["quantity_delivered"] == 9.0
    await _assert_neighbour_is_derived(db, lines, family)


@pytest.mark.parametrize("family", FAMILIES)
async def test_shared_demand_lock_add_a_line_with_a_share_of_the_demand(
    db: AsyncSession, manager: httpx.AsyncClient, create_user: Any, family: str
) -> None:
    owner = await create_user(username="graph-owner", email="graph-owner@example.com")
    graph = Graph(db, owner, owner)
    item = await (graph.bought_item() if family == "bought" else graph.source_item())
    project = await graph.project()
    lines = await _shared_lines(db, family, order_status="draft", line_status="pending")
    # The shared demand has 3 pieces left for the new line, of the line's item.
    model = BoughtItemDemandItemOrmModel if family == "bought" else SourceItemDemandItemOrmModel
    shared = await db.get(model, lines.shared)
    assert shared is not None
    shared.quantity += 3.0
    if isinstance(shared, BoughtItemDemandItemOrmModel):
        shared.item_id = item.id
    else:
        shared.source_item_id = item.id
    await db.commit()
    await seed.settle(db)
    target = (await manager.post(f"{ORDERS}/", json={"supplier_id": 1})).json()["id"]
    item_field = "bought_item_id" if family == "bought" else "source_item_id"

    added = await manager.post(
        f"{ORDERS}/{target}/items",
        json={
            "order_id": target,
            "supplier_id": 1,
            "project_id": project.id,
            item_field: item.id,
            "quantity": 3,
            "unit": "pcs",
            f"{family}_demand_allocations": [{"demand_item_id": lines.shared, "quantity": 3}],
        },
    )

    assert added.status_code == 201, added.text
    await _assert_neighbour_is_derived(db, lines, family)


# ── Lots ─────────────────────────────────────────────────────────────────


@dataclass
class _Lots:
    """Lot `first` and lot `second`. The made demand `shared` has 5 on each
    lot, `neighbour`, with the lower id, has 5 on the second lot only."""

    first: int
    second: int
    neighbour: int
    shared: int


async def _shared_made_demands(
    db: AsyncSession, first: ProductionLotOrmModel, second: ProductionLotOrmModel
) -> _Lots:
    neighbour = await seed.made_demand(db, "open", second, 5.0)
    shared = await seed.made_demand(db, "open", first, 10.0)
    await db.execute(
        MadeItemAllocationOrmModel.__table__.update()
        .where(MadeItemAllocationOrmModel.demand_item_id == shared.id)
        .values(quantity=5.0)
    )
    await seed.add(
        db,
        MadeItemAllocationOrmModel(
            demand_item_id=shared.id, lot_id=second.id, source="lot", quantity=5.0
        ),
    )
    await db.commit()
    await seed.settle(db)
    return _Lots(first.id, second.id, neighbour.id, shared.id)


async def _assert_made_neighbour_is_derived(db: AsyncSession, lots: _Lots) -> None:
    allocation = await db.scalar(
        select(MadeItemAllocationOrmModel)
        .where(MadeItemAllocationOrmModel.demand_item_id == lots.neighbour)
        .execution_options(populate_existing=True)
    )
    assert allocation is not None
    assert (allocation.lot_id, allocation.quantity) == (lots.second, 5.0)


async def _lot_with_delivered_made_line(db: AsyncSession) -> ProductionLotOrmModel:
    """A lot of 10 whose only position's MADE line delivered 4 pieces."""
    lot = await seed.lot(db, "in_progress")
    position = await seed.position(db, lot, "external", "in_progress")
    order = await seed.order(db, "partially_delivered", ordered_date=seed.NOW)
    await seed.line(
        db, order, "partially_delivered", at=position, ordered_date=seed.NOW, quantity_delivered=4.0
    )
    return lot


async def test_shared_demand_lock_cancel_a_lot_of_a_made_demand(
    db: AsyncSession, manager: httpx.AsyncClient
) -> None:
    second = await seed.lot(db, "draft")
    first = await seed.lot(db, "draft")
    lots = await _shared_made_demands(db, first, second)

    canceled = await manager.post(
        f"{LOTS}/{lots.first}/cancel",
        json={"expected_edit_version": await lot_version(manager, lots.first), "reason": "x"},
    )

    assert canceled.status_code == 200, canceled.text
    assert canceled.json()["status"] == "canceled"
    await _assert_made_neighbour_is_derived(db, lots)


async def test_shared_demand_lock_force_complete_a_lot_of_a_made_demand(
    db: AsyncSession, manager: httpx.AsyncClient
) -> None:
    second = await seed.lot(db, "draft")
    first = await _lot_with_delivered_made_line(db)
    lots = await _shared_made_demands(db, first, second)

    completed = await manager.post(
        f"{LOTS}/{lots.first}/complete",
        json={"expected_edit_version": await lot_version(manager, lots.first)},
    )

    assert completed.status_code == 200, completed.text
    assert completed.json()["status"] == "completed"
    await _assert_made_neighbour_is_derived(db, lots)


async def test_shared_demand_lock_scrap_moves_a_made_demand_to_the_replacement_lot(
    db: AsyncSession, manager: httpx.AsyncClient, create_user: Any
) -> None:
    owner = await create_user(username="scrap-owner", email="scrap-owner@example.com")
    second = await seed.lot(db, "draft")
    lot, order = await _seed_lot_and_order(db, owner.id, lot_number="LOT-SHARED", quantity=5.0)
    first = await db.get(ProductionLotOrmModel, lot.id)
    assert first is not None
    lots = await _shared_made_demands(db, first, second)
    started = await manager.post(f"{PRODUCTION_ORDERS}/{order.id}/start", json={})
    assert started.status_code == 200, started.text

    scrapped = await manager.post(
        f"{PRODUCTION_ORDERS}/{order.id}/scrap",
        json={
            "quantity": 2.0,
            "reason": "tool_breakage",
            "create_replacement": True,
            "expected_edit_version": await production_order_version(manager, order.id),
            "expected_lot_edit_version": await lot_version(manager, lots.first),
        },
    )

    assert scrapped.status_code == 200, scrapped.text
    assert len(scrapped.json()["created_lots"]) == 1
    await _assert_made_neighbour_is_derived(db, lots)


@dataclass
class _RawMaterial:
    """Lot `first` and another lot draw their raw material from one source
    line; the other lot's demand has the lower id."""

    first: int
    neighbour: int
    shared: int


async def _raw_material_line(db: AsyncSession, first: ProductionLotOrmModel) -> _RawMaterial:
    other = await seed.lot(db, "draft")
    order = await seed.order(db, "partially_delivered", ordered_date=seed.NOW)
    line = await seed.line(
        db,
        order,
        "partially_delivered",
        quantity=6.0,
        quantity_delivered=4.0,
        ordered_date=seed.NOW,
    )
    line.line_type = "SOURCE"
    line.bought_item_id = None
    line.source_item_id = 1
    neighbour = await seed.source_demand(db, "open", lot_id=other.id, quantity=3.0)
    shared = await seed.source_demand(db, "open", lot_id=first.id, quantity=3.0)
    other.input_demand_id = neighbour.id
    first.input_demand_id = shared.id
    await seed.source_allocation(db, neighbour, line, 3.0)
    await seed.source_allocation(db, shared, line, 3.0)
    await db.commit()
    await seed.settle(db)
    return _RawMaterial(first.id, neighbour.id, shared.id)


async def _assert_raw_material_neighbour_is_derived(db: AsyncSession, raw: _RawMaterial) -> None:
    allocation = await db.scalar(
        select(SourceItemAllocationOrmModel)
        .where(SourceItemAllocationOrmModel.demand_item_id == raw.neighbour)
        .execution_options(populate_existing=True)
    )
    assert allocation is not None
    assert allocation.quantity == 3.0


async def test_shared_demand_lock_cancel_a_lot_whose_raw_material_line_serves_another(
    db: AsyncSession, manager: httpx.AsyncClient
) -> None:
    raw = await _raw_material_line(db, await seed.lot(db, "draft"))

    canceled = await manager.post(
        f"{LOTS}/{raw.first}/cancel",
        json={"expected_edit_version": await lot_version(manager, raw.first), "reason": "x"},
    )

    assert canceled.status_code == 200, canceled.text
    await _assert_raw_material_neighbour_is_derived(db, raw)


async def test_shared_demand_lock_force_complete_a_lot_whose_raw_material_line_serves_another(
    db: AsyncSession, manager: httpx.AsyncClient
) -> None:
    raw = await _raw_material_line(db, await _lot_with_delivered_made_line(db))

    completed = await manager.post(
        f"{LOTS}/{raw.first}/complete",
        json={"expected_edit_version": await lot_version(manager, raw.first)},
    )

    assert completed.status_code == 200, completed.text
    assert completed.json()["status"] == "completed"
    await _assert_raw_material_neighbour_is_derived(db, raw)
