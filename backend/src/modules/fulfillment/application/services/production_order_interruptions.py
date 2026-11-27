"""Closing the interruption of a production order that leaves work for good,
shared by its cancel, by the cascades of a lot cancel and a forced lot
completion, and by a piece disposition that cuts it back to what it already
processed. Nothing here commits.
"""

from datetime import datetime

from src.modules.fulfillment.domain.value_objects.interruption_ended_by import InterruptionEndedBy
from src.modules.fulfillment.ports.outbound.repositories.production_order_interruption_repository import (
    IProductionOrderInterruptionRepository,
)


async def close_open_interruptions(
    interruptions: IProductionOrderInterruptionRepository,
    production_order_id: int,
    now: datetime,
    actor_id: int,
    *,
    ended_by: InterruptionEndedBy,
) -> None:
    """Ends the order's open interruption at `now`, if it has one, so a
    canceled or cut order is not left paused and its net work time counts
    the pause up to here. `ended_by` says whether a cancel or a cut ended
    it, since no work follows either. An order has at most one open
    interruption, which a partial unique index holds."""
    await interruptions.close_open(production_order_id, now, actor_id, ended_by=ended_by)
