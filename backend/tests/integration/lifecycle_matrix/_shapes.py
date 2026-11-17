"""
The data shapes the writer matrix runs every lifecycle writer against. A
shape seeds the rows straight through the ORM (tests/integration/_lifecycle_seed.py),
lets the reconciler store what their facts derive, or drives a few requests
for the rows a seed cannot give consistently (a lot on hold, a line closed
short), and returns a World naming the rows a writer acts on. Every shape
starts from the same catalogue: supplier, bought item, source item, made
item and project #1, which the seeds name.
"""

from collections.abc import Awaitable
from collections.abc import Callable
from dataclasses import dataclass
from dataclasses import field
from typing import Any

from sqlalchemy import select
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.catalogue.adapters.outbound.persistence.models.admin_settings_model.orders import (
    AdminOrderSettingsOrmModel,
)
from src.modules.catalogue.adapters.outbound.persistence.models.fabrication_method_model import (
    FabricationMethodOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.bought_item_allocation_model import (
    BoughtItemAllocationOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.made_item_allocation_model import (
    MadeItemAllocationOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.order_item_delivery_model import (
    OrderItemDeliveryOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.machine_pool_repository import (
    SqlAlchemyMachinePoolRepository,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.production_machine_repository import (
    SqlAlchemyProductionMachineRepository,
)
from src.modules.fulfillment.domain.entities.machine_pool import MachinePool
from src.modules.fulfillment.domain.entities.production_machine import ProductionMachine
from src.modules.platform.domain.entities.user import User
from tests.integration import _lifecycle_seed as seed
from tests.integration._edit_versions import line_version
from tests.integration._edit_versions import lot_version
from tests.integration._tenant_day import tenant_today
from tests.integration.repository_reads._graph import Graph
from tests.integration.repository_reads._graph import make
from tests.integration.test_api_scrap_pieces import _seed_lot_and_order

WEB = "/api/v1/web"


@dataclass
class World:
    """The rows a writer acts on, each None where the shape has none.
    `order` and `line` are the order and line a request names; `demand` is
    the demand a request names, as (family, id), and `neighbour` the
    lower-id demand sharing its line or lot."""

    client: Any
    order: int | None = None
    line: int | None = None
    other_order: int | None = None
    demand: tuple[str, int] | None = None
    neighbour: tuple[str, int] | None = None
    lot: int | None = None
    # A delivery row with accepted pieces on `line`, which a correction
    # names; the matrix fills it in after the shape is built.
    delivery: int | None = None
    free_position: int | None = None
    external_position: int | None = None
    production_order: int | None = None
    completion: int | None = None
    # Codes that answer this shape's documented refusals besides 409 and
    # 422, such as 404 for a line asked for under the order it left.
    also_refused: frozenset[int] = frozenset()
    notes: dict[str, Any] = field(default_factory=dict)


async def catalogue(db: AsyncSession, owner: User) -> Graph:
    """Supplier, bought item, source item, made item and project #1."""
    graph = Graph(db, owner, owner)
    ids = [
        (await graph.supplier()).id,
        (await graph.bought_item()).id,
        (await graph.source_item()).id,
        (await graph.made_item()).id,
        (await graph.project()).id,
    ]
    assert ids == [1, 1, 1, 1, 1], ids
    return graph


def _as_source(*lines: Any) -> None:
    for line in lines:
        line.line_type, line.bought_item_id, line.source_item_id = "SOURCE", None, 1


async def _split_over_two_lines(db: AsyncSession, client: Any, family: str) -> World:
    first_order = await seed.order(db, "ordered", ordered_date=seed.NOW)
    second_order = await seed.order(db, "ordered", ordered_date=seed.NOW)
    first = await seed.line(db, first_order, "ordered", ordered_date=seed.NOW)
    second = await seed.line(db, second_order, "ordered", ordered_date=seed.NOW)
    if family == "bought":
        neighbour = await seed.bought_demand(db, "open", second, 5.0)
        shared = await seed.bought_demand(db, "open", first, 12.0)
        await seed.add(
            db,
            BoughtItemAllocationOrmModel(
                demand_item_id=shared.id, order_item_id=second.id, source="order", quantity=5.0
            ),
        )
        await db.execute(
            update(BoughtItemAllocationOrmModel)
            .where(BoughtItemAllocationOrmModel.demand_item_id == shared.id)
            .where(BoughtItemAllocationOrmModel.order_item_id == first.id)
            .values(quantity=5.0)
        )
    else:
        _as_source(first, second)
        lots = [
            await seed.lot(db, "draft", source_item_id=1),
            await seed.lot(db, "draft", source_item_id=1),
        ]
        neighbour = await seed.source_demand(
            db, "open", lot_id=lots[0].id, quantity=5.0, source_item_id=1
        )
        shared = await seed.source_demand(
            db, "open", lot_id=lots[1].id, quantity=12.0, source_item_id=1
        )
        lots[0].input_demand_id, lots[1].input_demand_id = neighbour.id, shared.id
        await seed.source_allocation(db, neighbour, second, 5.0)
        await seed.source_allocation(db, shared, first, 5.0)
        await seed.source_allocation(db, shared, second, 5.0)
    await db.commit()
    await seed.settle(db)
    return World(
        client,
        order=first_order.id,
        line=first.id,
        other_order=second_order.id,
        demand=(family, shared.id),
        neighbour=(family, neighbour.id),
    )


async def lines_bought(db: AsyncSession, client: Any) -> World:
    return await _split_over_two_lines(db, client, "bought")


async def lines_source(db: AsyncSession, client: Any) -> World:
    return await _split_over_two_lines(db, client, "source")


async def lots_made(db: AsyncSession, client: Any) -> World:
    """A made demand of 12 split 5 and 5 over two draft lots, the lower-id
    neighbour on the second lot only, and a free position on the first."""
    second = await seed.lot(db, "draft")
    first = await seed.lot(db, "draft")
    position = await seed.position(db, first, "unassigned", "pending")
    neighbour = await seed.made_demand(db, "open", second, 5.0)
    shared = await seed.made_demand(db, "open", first, 12.0)
    await db.execute(
        update(MadeItemAllocationOrmModel)
        .where(MadeItemAllocationOrmModel.demand_item_id == shared.id)
        .values(quantity=5.0)
    )
    await seed.add(
        db,
        MadeItemAllocationOrmModel(
            demand_item_id=shared.id, lot_id=second.id, source="lot", quantity=5.0
        ),
    )
    order = await seed.order(db, "draft")
    await db.commit()
    await seed.settle(db)
    return World(
        client,
        lot=first.id,
        free_position=position.id,
        other_order=order.id,
        demand=("made", shared.id),
        neighbour=("made", neighbour.id),
    )


async def bought_beside_source(db: AsyncSession, client: Any) -> World:
    """One ordered bought line of 10 that carries a bought demand of 5 and
    a lot's source demand of 5, filled bought first."""
    order = await seed.order(db, "ordered", ordered_date=seed.NOW)
    line = await seed.line(db, order, "ordered", ordered_date=seed.NOW)
    bought = await seed.bought_demand(db, "open", line, 5.0)
    lot = await seed.lot(db, "draft")
    # The lot draws the bought item, so its source demand names that item.
    source = await seed.source_demand(db, "open", lot_id=lot.id, quantity=5.0, bought_item_id=1)
    lot.input_demand_id = source.id
    await seed.source_allocation(db, source, line, 5.0)
    other = await seed.order(db, "draft")
    await db.commit()
    await seed.settle(db)
    return World(
        client,
        order=order.id,
        line=line.id,
        other_order=other.id,
        demand=("source", source.id),
        neighbour=("bought", bought.id),
        lot=lot.id,
    )


async def moved_line(db: AsyncSession, client: Any) -> World:
    """A line that a move put on another order after the client read it:
    requests name the order it left, which answer 404."""
    left = await seed.order(db, "ordered", ordered_date=seed.NOW)
    now_on = await seed.order(db, "ordered", ordered_date=seed.NOW)
    line = await seed.line(db, now_on, "ordered", ordered_date=seed.NOW)
    demand = await seed.bought_demand(db, "open", line, 10.0)
    await db.commit()
    await seed.settle(db)
    return World(
        client,
        order=left.id,
        line=line.id,
        other_order=now_on.id,
        demand=("bought", demand.id),
        also_refused=frozenset({404}),
        notes={"line_order": now_on.id},
    )


async def _line_with(db: AsyncSession, client: Any, status: str, delivered: float) -> World:
    order = await seed.order(db, status, ordered_date=seed.NOW)
    line = await seed.line(db, order, status, ordered_date=seed.NOW, quantity_delivered=delivered)
    demand = await seed.bought_demand(db, "open", line, 10.0)
    other = await seed.order(db, "draft")
    await db.commit()
    await seed.settle(db)
    return World(
        client, order=order.id, line=line.id, other_order=other.id, demand=("bought", demand.id)
    )


async def partially_delivered_line(db: AsyncSession, client: Any) -> World:
    return await _line_with(db, client, "partially_delivered", 4.0)


async def lost_pieces_line(db: AsyncSession, client: Any) -> World:
    """A line of 10 that accepted 2 and lost 3 at receipt."""
    world = await _line_with(db, client, "ordered", 0.0)
    booked = await client.put(
        f"{WEB}/bought-items-allocations/order-item/{world.line}/deliver",
        params={"quantity": 2},
        json={
            "quantity_rejected": 3,
            "rejection_reason": "transport_damage",
            "rejection_outcome": "lost",
        },
    )
    assert booked.status_code == 200, booked.text
    return world


async def closed_short_line(db: AsyncSession, client: Any) -> World:
    """A line closed short at the 4 pieces it delivered."""
    world = await _line_with(db, client, "partially_delivered", 4.0)
    assert world.order is not None and world.line is not None
    closed = await client.post(
        f"{WEB}/orders/{world.order}/items/{world.line}/close-short",
        params={"expected_edit_version": await line_version(client, world.order, world.line)},
    )
    assert closed.status_code == 200, closed.text
    return world


async def tolerance_line(db: AsyncSession, client: Any) -> World:
    """An ordered line of 10 under a 10 % over- and under-delivery
    tolerance, so 9 to 11 pieces settle it."""
    settings = await db.get(AdminOrderSettingsOrmModel, 1)
    assert settings is not None
    settings.over_delivery_tolerance_percent = 10.0
    settings.under_delivery_tolerance_percent = 10.0
    world = await _line_with(db, client, "ordered", 0.0)
    world.notes["tolerance"] = True
    return world


async def smallest_quantity(db: AsyncSession, client: Any) -> World:
    """A line and a demand of 0.000002 m, the smallest quantity the columns
    store and the lifecycle tells from nothing."""
    order = await seed.order(db, "ordered", ordered_date=seed.NOW)
    line = await seed.line(db, order, "ordered", ordered_date=seed.NOW, quantity=0.000002)
    line.unit = "m"
    demand = await seed.bought_demand(db, "open", line, 0.000002)
    demand.unit = "m"
    other = await seed.order(db, "draft")
    await db.commit()
    await seed.settle(db)
    return World(
        client,
        order=order.id,
        line=line.id,
        other_order=other.id,
        demand=("bought", demand.id),
        notes={"unit": "m", "quantity": 0.000002},
    )


async def _running_lot(db: AsyncSession, client: Any, owner: User) -> World:
    """A rework lot of 5 with one internal position whose production order
    runs and completed 2 pieces, and a made demand of 5 on the lot."""
    lot, order = await _seed_lot_and_order(db, owner.id, lot_number="LOT-MX", quantity=5.0)
    demand = await seed.made_demand(db, "open", None, 5.0)
    await seed.add(
        db,
        MadeItemAllocationOrmModel(
            demand_item_id=demand.id, lot_id=lot.id, source="lot", quantity=5.0
        ),
    )
    await db.commit()
    await seed.settle(db)
    started = await client.post(f"{WEB}/production-orders/{order.id}/start", json={})
    assert started.status_code == 200, started.text
    completed = await client.post(
        f"{WEB}/production-orders/{order.id}/completions",
        json={"quantity": 2, "completion_date": tenant_today().isoformat()},
    )
    assert completed.status_code == 200, completed.text
    completion = next(c["id"] for c in completed.json()["completions"])
    other = await seed.order(db, "draft")
    await db.commit()
    return World(
        client,
        lot=lot.id,
        production_order=order.id,
        completion=completion,
        demand=("made", demand.id),
        other_order=other.id,
    )


async def running_lot(db: AsyncSession, client: Any, owner: User) -> World:
    return await _running_lot(db, client, owner)


async def held_lot(db: AsyncSession, client: Any, owner: User) -> World:
    world = await _running_lot(db, client, owner)
    held = await client.post(f"{WEB}/production-lots/{world.lot}/hold", json={"reason": "check"})
    assert held.status_code == 200, held.text
    return world


async def canceled_lot(db: AsyncSession, client: Any) -> World:
    world = await lots_made(db, client)
    assert world.lot is not None
    canceled = await client.post(
        f"{WEB}/production-lots/{world.lot}/cancel",
        json={"expected_edit_version": await lot_version(client, world.lot), "reason": "x"},
    )
    assert canceled.status_code == 200, canceled.text
    return world


async def completed_lot(db: AsyncSession, client: Any) -> World:
    """A lot whose bought-in position delivered 4 of 10, force-completed."""
    lot = await seed.lot(db, "in_progress")
    position = await seed.position(db, lot, "external", "in_progress")
    order = await seed.order(db, "partially_delivered", ordered_date=seed.NOW)
    line = await seed.line(
        db, order, "partially_delivered", at=position, ordered_date=seed.NOW, quantity_delivered=4.0
    )
    demand = await seed.made_demand(db, "open", lot, 10.0)
    await db.commit()
    await seed.settle(db)
    completed = await client.post(
        f"{WEB}/production-lots/{lot.id}/complete",
        json={"expected_edit_version": await lot_version(client, lot.id)},
    )
    assert completed.status_code == 200, completed.text
    return World(
        client,
        lot=lot.id,
        external_position=position.id,
        order=order.id,
        line=line.id,
        demand=("made", demand.id),
    )


async def made_line_beside_bought(db: AsyncSession, client: Any) -> World:
    """One ordered order with a MADE line on a lot's bought-in position and
    a bought line carrying a bought demand, which sorts before the lot's
    made demand in the lock order: a rejection that loses pieces of the lot
    locks them all at once."""
    lot = await seed.lot(db, "in_progress")
    position = await seed.position(db, lot, "external", "ordered_or_queued")
    order = await seed.order(db, "ordered", ordered_date=seed.NOW)
    made = await seed.line(db, order, "ordered", at=position, ordered_date=seed.NOW)
    bought_line = await seed.line(db, order, "ordered", ordered_date=seed.NOW)
    bought = await seed.bought_demand(db, "open", bought_line, 5.0)
    made_demand = await seed.made_demand(db, "open", lot, 10.0)
    other = await seed.order(db, "draft")
    await db.commit()
    await seed.settle(db)
    return World(
        client,
        order=order.id,
        line=made.id,
        other_order=other.id,
        demand=("made", made_demand.id),
        neighbour=("bought", bought.id),
        lot=lot.id,
        external_position=position.id,
    )


async def raw_material_partly_delivered(db: AsyncSession, client: Any) -> World:
    """A planned lot whose raw material comes on two source lines, one
    delivered, its arrival stored as a moment, and one still expected as a
    day, with a queued production order the schedule walk dates from them."""
    lot = await seed.lot(db, "planned", source_item_id=1)
    position = await seed.position(db, lot, "internal", "ordered_or_queued")
    production_order = await seed.production_order(
        db, position, "queued", queue_sequence=1, estimated_duration_minutes=60
    )
    demand = await seed.source_demand(
        db, "ordered", lot_id=lot.id, quantity=10.0, source_item_id=1, unit="pcs"
    )
    lot.input_demand_id = demand.id
    order = await seed.order(db, "partially_delivered", ordered_date=seed.NOW)
    arrived = await seed.line(
        db,
        order,
        "delivered",
        ordered_date=seed.NOW,
        quantity=5.0,
        quantity_delivered=5.0,
        delivery_date=seed.NOW,
    )
    expected = await seed.line(
        db,
        order,
        "ordered",
        ordered_date=seed.NOW,
        quantity=5.0,
        expected_delivery_date=seed.NOW.date(),
    )
    _as_source(arrived, expected)
    await seed.source_allocation(db, demand, arrived, 5.0)
    await seed.source_allocation(db, demand, expected, 5.0)
    other = await seed.order(db, "draft")
    await db.commit()
    await seed.settle(db)
    return World(
        client,
        order=order.id,
        line=expected.id,
        other_order=other.id,
        demand=("source", demand.id),
        lot=lot.id,
        production_order=production_order.id,
    )


async def pool_order(db: AsyncSession, client: Any, owner: User) -> World:
    """A queued production order of a planned lot, assigned to a machine
    pool rather than a machine."""
    method_id = await db.scalar(
        select(FabricationMethodOrmModel.id).order_by(FabricationMethodOrmModel.id)
    )
    machine = await SqlAlchemyProductionMachineRepository(db).save(
        make(
            ProductionMachine,
            internal_name="POOL-MILL",
            fabrication_method_ids=[method_id] if method_id is not None else [],
            creator_id=owner.id,
        )
    )
    pool = await SqlAlchemyMachinePoolRepository(db).save(
        make(MachinePool, name="Pool", machine_ids=[machine.id], creator_id=owner.id)
    )
    lot = await seed.lot(db, "planned", source_made_item_id=1, source_item_id=None)
    position = await seed.position(db, lot, "internal", "ordered_or_queued")
    production_order = await seed.production_order(
        db,
        position,
        "queued",
        machine_pool_id=pool.id,
        queue_sequence=1,
        estimated_duration_minutes=60,
    )
    other = await seed.order(db, "draft")
    await db.commit()
    await seed.settle(db)
    return World(client, lot=lot.id, production_order=production_order.id, other_order=other.id)


type ShapeBuilder = Callable[..., Awaitable[World]]

# The shapes by name; the ones that take the owner build production work.
SHAPES: dict[str, ShapeBuilder] = {
    "lines_bought": lines_bought,
    "lines_source": lines_source,
    "lots_made": lots_made,
    "bought_beside_source": bought_beside_source,
    "moved_line": moved_line,
    "partially_delivered_line": partially_delivered_line,
    "lost_pieces_line": lost_pieces_line,
    "closed_short_line": closed_short_line,
    "tolerance_line": tolerance_line,
    "smallest_quantity": smallest_quantity,
    "running_lot": running_lot,
    "held_lot": held_lot,
    "canceled_lot": canceled_lot,
    "completed_lot": completed_lot,
    "made_line_beside_bought": made_line_beside_bought,
    "raw_material_partly_delivered": raw_material_partly_delivered,
    "pool_order": pool_order,
}
NEEDS_OWNER = frozenset({"running_lot", "held_lot", "pool_order"})


async def build_world(db: AsyncSession, client: Any, owner: User, shape: str) -> World:
    """The World of `shape`, with the delivery row a correction names."""
    build = SHAPES[shape]
    world = await (build(db, client, owner) if shape in NEEDS_OWNER else build(db, client))
    if world.line is not None:
        world.delivery = await db.scalar(
            select(OrderItemDeliveryOrmModel.id)
            .where(OrderItemDeliveryOrmModel.order_item_id == world.line)
            .where(OrderItemDeliveryOrmModel.quantity > 0)
            .order_by(OrderItemDeliveryOrmModel.id)
        )
    return world
