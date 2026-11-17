"""
Lifecycle rows written straight through the ORM, with whatever stored status
and intents a test needs, consistent with their facts or not. SQLite does not
enforce foreign keys, so the users, items, suppliers and projects the rows
reference need not exist. A line's delivered pieces come with their delivery
row, so the drift report's delivery totals check finds nothing on a seeded
line, unless the test asks for the pieces without it. `settle` then stores what
the seeded facts derive, for a test that wants consistent statuses.
"""

import itertools
from datetime import UTC
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.fulfillment.adapters.outbound.persistence.lifecycle_store import (
    sql_lifecycle_repositories,
)
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
from src.modules.fulfillment.adapters.outbound.persistence.models.order_model import OrderOrmModel
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
from src.modules.fulfillment.application.services.lifecycle_reconciler import LifecycleReconciler
from src.modules.fulfillment.domain.value_objects.lifecycle_aggregate import LifecycleAggregate
from tests.integration._lot_facts import _SEEDER

NOW = datetime.now(UTC).replace(microsecond=0)
_numbers = itertools.count(1)


async def add[T](db: AsyncSession, row: T) -> T:
    db.add(row)
    await db.flush()
    return row


async def lot(db: AsyncSession, status: str, **values: Any) -> ProductionLotOrmModel:
    return await add(
        db,
        ProductionLotOrmModel(
            created=NOW,
            lot_number=f"LS-{next(_numbers)}",
            quantity=values.pop("quantity", 10.0),
            status=status,
            creator_id=1,
            made_item_id=1,
            project_id=1,
            **values,
        ),
    )


async def position(
    db: AsyncSession, of: ProductionLotOrmModel, kind: str, status: str, **values: Any
) -> LotPositionOrmModel:
    return await add(
        db,
        LotPositionOrmModel(
            created=NOW,
            sequence=values.pop("sequence", 1),
            kind=kind,
            status=status,
            quantity=values.pop("quantity", 10.0),
            quantity_completed=values.pop("quantity_completed", 0.0),
            creator_id=1,
            lot_id=of.id,
            **values,
        ),
    )


async def production_order(
    db: AsyncSession, at: LotPositionOrmModel, status: str, **values: Any
) -> ProductionOrderOrmModel:
    return await add(
        db,
        ProductionOrderOrmModel(
            created=NOW,
            production_order_number=f"POS-{next(_numbers)}",
            status=status,
            quantity=values.pop("quantity", 10.0),
            quantity_completed=values.pop("quantity_completed", 0.0),
            creator_id=1,
            lot_position_id=at.id,
            **values,
        ),
    )


async def order(db: AsyncSession, status: str, **values: Any) -> OrderOrmModel:
    return await add(
        db,
        OrderOrmModel(
            order_number=f"OS-{next(_numbers)}",
            created=NOW,
            status=status,
            creator_id=1,
            supplier_id=1,
            **values,
        ),
    )


async def line(
    db: AsyncSession,
    of: OrderOrmModel,
    status: str,
    *,
    at: LotPositionOrmModel | None = None,
    booked: bool = True,
    **values: Any,
) -> OrderItemOrmModel:
    """A BOUGHT line, or a MADE line on the position `at`. With `booked`
    False its delivered pieces have no delivery row."""
    row = await add(
        db,
        OrderItemOrmModel(
            created=NOW,
            status=status,
            quantity=values.pop("quantity", 10.0),
            quantity_delivered=values.pop("quantity_delivered", 0.0),
            unit="pcs",
            creator_id=1,
            order_id=of.id,
            supplier_id=1,
            project_id=values.pop("project_id", 1),
            line_type="MADE" if at is not None else "BOUGHT",
            bought_item_id=None if at is not None else values.pop("bought_item_id", 1),
            lot_position_id=at.id if at is not None else None,
            **values,
        ),
    )
    if booked and row.quantity_delivered > 0:
        await add(
            db,
            OrderItemDeliveryOrmModel(
                created=NOW,
                order_item_id=row.id,
                quantity=row.quantity_delivered,
                delivery_date=NOW,
            ),
        )
    return row


async def bought_demand(
    db: AsyncSession, status: str, on: OrderItemOrmModel | None, quantity: float, **values: Any
) -> BoughtItemDemandItemOrmModel:
    demand = await add(
        db,
        BoughtItemDemandItemOrmModel(
            created=NOW.date(),
            status=status,
            quantity=quantity,
            unit="pcs",
            creator_id=1,
            item_id=values.pop("item_id", 1),
            project_id=1,
            **values,
        ),
    )
    if on is not None:
        await add(
            db,
            BoughtItemAllocationOrmModel(
                demand_item_id=demand.id, order_item_id=on.id, source="order", quantity=quantity
            ),
        )
    return demand


async def made_demand(
    db: AsyncSession, status: str, on: ProductionLotOrmModel | None, quantity: float
) -> MadeItemDemandItemOrmModel:
    demand = await add(
        db,
        MadeItemDemandItemOrmModel(
            created=NOW.date(),
            status=status,
            quantity=quantity,
            unit="pcs",
            creator_id=1,
            made_item_id=1,
            project_id=1,
        ),
    )
    if on is not None:
        await add(
            db,
            MadeItemAllocationOrmModel(
                demand_item_id=demand.id, lot_id=on.id, source="lot", quantity=quantity
            ),
        )
    return demand


async def source_demand(
    db: AsyncSession, status: str, **values: Any
) -> SourceItemDemandItemOrmModel:
    return await add(
        db,
        SourceItemDemandItemOrmModel(
            created=NOW.date(),
            status=status,
            quantity=values.pop("quantity", 3.0),
            unit=values.pop("unit", "kg"),
            creator_id=1,
            lot_id=values.pop("lot_id", 1),
            project_id=1,
            **values,
        ),
    )


async def source_allocation(
    db: AsyncSession, demand: SourceItemDemandItemOrmModel, on: OrderItemOrmModel, quantity: float
) -> SourceItemAllocationOrmModel:
    return await add(
        db,
        SourceItemAllocationOrmModel(
            demand_item_id=demand.id, order_item_id=on.id, source="order", quantity=quantity
        ),
    )


class _NoBus:
    async def publish(self, event: object) -> None:
        return None


async def settle(db: AsyncSession) -> None:
    """Stores what the seeded facts derive for every lifecycle row and
    commits, so a test that seeded facts starts from consistent statuses."""
    reconciler = LifecycleReconciler(sql_lifecycle_repositories(db), _NoBus())
    reconciler.touch_lots(await db.scalars(select(ProductionLotOrmModel.id)))
    reconciler.touch_production_orders(await db.scalars(select(ProductionOrderOrmModel.id)))
    reconciler.touch_orders(await db.scalars(select(OrderOrmModel.id)))
    reconciler.touch_order_items(await db.scalars(select(OrderItemOrmModel.id)))
    for family, model in (
        (LifecycleAggregate.BOUGHT_DEMANDS, BoughtItemDemandItemOrmModel),
        (LifecycleAggregate.MADE_DEMANDS, MadeItemDemandItemOrmModel),
        (LifecycleAggregate.SOURCE_DEMANDS, SourceItemDemandItemOrmModel),
    ):
        reconciler.touch_demands(family, await db.scalars(select(model.id)))
    await reconciler.run(_SEEDER, NOW, reason="seeded")
    await db.commit()
