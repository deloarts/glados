"""
Gives a production order seeded straight into the database the facts its
stored status stands for, so the lifecycle reconciler derives that status
and the drift check after the test agrees with it: a started order its
actual_start, a paused one an open manual interruption, a completed one a
completion row of its quantity and its actual_end, a canceled one its
canceled_at. Facts a seed set already are kept.
"""

from datetime import UTC
from datetime import datetime
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.fulfillment.adapters.outbound.persistence.models.production_order_completion_model import (
    ProductionOrderCompletionOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.production_order_interruption_model import (
    ProductionOrderInterruptionOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.production_order_model import (
    ProductionOrderOrmModel,
)
from src.modules.fulfillment.domain.value_objects.interruption_reason import InterruptionReason
from src.modules.fulfillment.domain.value_objects.production_status import ProductionOrderStatus

_STARTED = frozenset(
    {
        ProductionOrderStatus.IN_PROGRESS.value,
        ProductionOrderStatus.PAUSED.value,
        ProductionOrderStatus.COMPLETED.value,
    }
)


async def give_production_order_facts(db: AsyncSession, production_order_id: int) -> None:
    """Records the facts of the order's stored status, see the module
    docstring, and flushes. Started two hours ago, paused one hour ago, and
    completed or canceled now."""
    order = await db.get(ProductionOrderOrmModel, production_order_id, populate_existing=True)
    assert order is not None, production_order_id
    now = datetime.now(UTC)
    if order.status in _STARTED and order.actual_start is None:
        order.actual_start = now - timedelta(hours=2)
    if order.status == ProductionOrderStatus.PAUSED.value:
        open_pause = await db.scalar(
            select(ProductionOrderInterruptionOrmModel.id).where(
                ProductionOrderInterruptionOrmModel.production_order_id == order.id,
                ProductionOrderInterruptionOrmModel.resumed_at.is_(None),
            )
        )
        if open_pause is None:
            db.add(
                ProductionOrderInterruptionOrmModel(
                    created=now - timedelta(hours=1),
                    production_order_id=order.id,
                    paused_at=now - timedelta(hours=1),
                    paused_by_id=order.creator_id,
                    reason=InterruptionReason.MANUAL.value,
                )
            )
    if order.status == ProductionOrderStatus.COMPLETED.value:
        recorded = await db.scalar(
            select(ProductionOrderCompletionOrmModel.id)
            .where(ProductionOrderCompletionOrmModel.production_order_id == order.id)
            .limit(1)
        )
        if recorded is None:
            db.add(
                ProductionOrderCompletionOrmModel(
                    created=now,
                    production_order_id=order.id,
                    quantity=order.quantity,
                    quantity_accepted=order.quantity_completed,
                    quantity_rejected=order.quantity - order.quantity_completed,
                    completion_date=now.date(),
                    operator_id=order.creator_id,
                    recorded_by_id=order.creator_id,
                )
            )
        if order.actual_end is None:
            order.actual_end = now
    if order.status == ProductionOrderStatus.CANCELED.value and order.canceled_at is None:
        order.canceled_at = now
    await db.flush()
