"""
The quantity invariants the writer matrix checks after every request, read
straight from the tables: nothing negative, a line's delivered total equal
to its delivery rows, no live line, lot or demand holding more allocations
than it can carry, no position or production order completing more than its
quantity, and no window left on an ended production order. The stored
statuses are checked against their derivation by the drift check after the
test (tests/integration/conftest.py).
"""

from collections import defaultdict

from sqlalchemy import func
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.fulfillment.adapters.outbound.persistence.models.bought_item_allocation_model import (
    BoughtItemAllocationOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.bought_item_demand_item_model import (
    BoughtItemDemandItemOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.lot_position_model import (
    LotPositionOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.made_item_allocation_model import (
    MadeItemAllocationOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.made_item_demand_item_model import (
    MadeItemDemandItemOrmModel,
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
from src.modules.fulfillment.adapters.outbound.persistence.models.production_order_model import (
    ProductionOrderOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.source_item_allocation_model import (
    SourceItemAllocationOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.source_item_demand_item_model import (
    SourceItemDemandItemOrmModel,
)

EPS = 1e-6


async def _all[T](db: AsyncSession, model: type[T]) -> list[T]:
    return list((await db.scalars(select(model).execution_options(populate_existing=True))).all())


async def assert_quantities_conserved(db: AsyncSession) -> None:
    """Raises AssertionError naming every invariant that does not hold."""
    problems: list[str] = []
    lines = {line.id: line for line in await _all(db, OrderItemOrmModel)}
    rows = dict(
        (
            await db.execute(
                select(
                    OrderItemDeliveryOrmModel.order_item_id,
                    func.sum(OrderItemDeliveryOrmModel.quantity),
                ).group_by(OrderItemDeliveryOrmModel.order_item_id)
            )
        ).all()
    )
    on_line: dict[int, float] = defaultdict(float)
    by_demand: dict[tuple[str, int], float] = defaultdict(float)
    for family, model in (
        ("bought", BoughtItemAllocationOrmModel),
        ("source", SourceItemAllocationOrmModel),
    ):
        for allocation in await _all(db, model):
            if allocation.quantity < -EPS:
                problems.append(f"{family} allocation #{allocation.id} is negative")
            by_demand[(family, allocation.demand_item_id)] += allocation.quantity
            if allocation.order_item_id is not None:
                on_line[allocation.order_item_id] += allocation.quantity
    on_lot: dict[int, float] = defaultdict(float)
    for made in await _all(db, MadeItemAllocationOrmModel):
        by_demand[("made", made.demand_item_id)] += made.quantity
        if made.lot_id is not None:
            on_lot[made.lot_id] += made.quantity

    totals = ("quantity", "quantity_delivered", "quantity_rejected", "quantity_rejected_lost")
    for line in lines.values():
        problems.extend(
            f"line #{line.id} {name} is negative" for name in totals if getattr(line, name) < -EPS
        )
        if abs(rows.get(line.id, 0.0) - line.quantity_delivered) > EPS:
            problems.append(
                f"line #{line.id} delivered {line.quantity_delivered} but its rows sum "
                f"{rows.get(line.id, 0.0)}"
            )
        carried = max(line.quantity, line.quantity_delivered)
        if line.canceled_at is None and on_line[line.id] > carried + EPS:
            problems.append(f"line #{line.id} carries {on_line[line.id]} of {carried}")

    for family, model in (
        ("bought", BoughtItemDemandItemOrmModel),
        ("made", MadeItemDemandItemOrmModel),
        ("source", SourceItemDemandItemOrmModel),
    ):
        for demand in await _all(db, model):
            allocated = by_demand[(family, demand.id)]
            if demand.canceled_at is None and allocated > demand.quantity + EPS:
                problems.append(
                    f"{family} demand #{demand.id} holds {allocated} of {demand.quantity}"
                )

    problems.extend(
        f"lot #{lot.id} carries {on_lot[lot.id]} of {lot.quantity}"
        for lot in await _all(db, ProductionLotOrmModel)
        if lot.canceled_at is None and on_lot[lot.id] > lot.quantity + EPS
    )
    problems.extend(
        f"position #{p.id} completed {p.quantity_completed} of {p.quantity}"
        for p in await _all(db, LotPositionOrmModel)
        if p.quantity_completed > p.quantity + EPS
    )
    for order in await _all(db, ProductionOrderOrmModel):
        if order.quantity_completed > order.quantity + EPS:
            problems.append(f"production order #{order.id} completed beyond its quantity")
        if order.status in ("completed", "canceled") and order.planned_start is not None:
            problems.append(f"production order #{order.id} is {order.status} but keeps a window")

    assert not problems, problems
