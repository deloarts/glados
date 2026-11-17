"""
The partial unique index uq_production_order_interruption_open holds a
production order to at most one open interruption (resumed_at IS NULL).
Closed interruptions do not count, so an order can be paused again once its
pause is closed, and every order has its own one. Asserted against the
schema directly through raw ORM inserts, since the integration schema comes
from `Base.metadata` and so carries the index on SQLite too.
"""

from datetime import timedelta

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.fulfillment.adapters.outbound.persistence.models.production_order_interruption_model import (
    ProductionOrderInterruptionOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.production_order_model import (
    ProductionOrderOrmModel,
)
from tests.integration import _lifecycle_seed as seed

pytestmark = pytest.mark.usefixtures("allow_lifecycle_drift")


async def _order(db: AsyncSession, queue_sequence: int = 1) -> ProductionOrderOrmModel:
    lot = await seed.lot(db, "in_progress")
    position = await seed.position(db, lot, "internal", "in_progress")
    return await seed.production_order(
        db, position, "paused", actual_start=seed.NOW, queue_sequence=queue_sequence
    )


async def _interruption(
    db: AsyncSession, order: ProductionOrderOrmModel, *, open_: bool, reason: str = "manual"
) -> None:
    db.add(
        ProductionOrderInterruptionOrmModel(
            created=seed.NOW,
            production_order_id=order.id,
            paused_at=seed.NOW,
            resumed_at=None if open_ else seed.NOW + timedelta(minutes=5),
            paused_by_id=1,
            resumed_by_id=None if open_ else 1,
            reason=reason,
        )
    )
    await db.flush()


async def test_a_second_open_interruption_on_one_order_is_rejected(db: AsyncSession) -> None:
    order = await _order(db)
    await _interruption(db, order, open_=True, reason="manual")

    with pytest.raises(IntegrityError):
        await _interruption(db, order, open_=True, reason="lot_hold")


async def test_closed_interruptions_leave_room_for_one_open(db: AsyncSession) -> None:
    order = await _order(db)
    await _interruption(db, order, open_=False)
    await _interruption(db, order, open_=False)
    await _interruption(db, order, open_=True)
    await db.commit()


async def test_each_order_can_have_its_own_open_interruption(db: AsyncSession) -> None:
    first, second = await _order(db, 1), await _order(db, 2)
    await _interruption(db, first, open_=True)
    await _interruption(db, second, open_=True)
    await db.commit()
