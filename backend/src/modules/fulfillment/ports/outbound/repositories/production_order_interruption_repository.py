"""
Repository interface for ProductionOrderInterruption, the pause/resume
audit trail owned by ProductionOrder (see production_order_lifecycle.py).
"""

from datetime import datetime
from typing import Protocol
from typing import runtime_checkable

from src.modules.fulfillment.domain.entities.production_order_interruption import (
    ProductionOrderInterruption,
)
from src.modules.fulfillment.domain.value_objects.interruption_ended_by import InterruptionEndedBy
from src.modules.fulfillment.domain.value_objects.interruption_reason import InterruptionReason


@runtime_checkable
class IProductionOrderInterruptionRepository(Protocol):
    async def add(self, interruption: ProductionOrderInterruption) -> ProductionOrderInterruption:
        """Opens a new interruption row: a pause (PauseProductionOrder) or
        the hold of the order's lot (HoldLot), as its reason says."""
        ...

    async def close_open(
        self,
        production_order_id: int,
        resumed_at: datetime,
        resumed_by_id: int,
        *,
        ended_by: InterruptionEndedBy,
        reason: InterruptionReason | None = None,
        resumed_operator_id: int | None = None,
    ) -> ProductionOrderInterruption | None:
        """Closes the order's open interruption (resumed_at IS NULL), only
        when its reason is the given one if `reason` is set, and returns it.
        None when there is no such row. An order has at most one open
        interruption: a resume closes the manual pause, a lot resume the
        interruption of its hold, and a cancel or a cut whichever is open.
        `ended_by` records which of these closed it, and
        `resumed_operator_id` the operator who went on with the work, which
        only the order's own resume knows."""
        ...

    async def get_by_order_ids(self, order_ids: list[int]) -> list[ProductionOrderInterruption]:
        """Every interruption (open or closed) for the given orders,
        oldest first, batched for the order-list/detail read path."""
        ...

    async def sum_minutes_by_order_ids(self, order_ids: list[int]) -> dict[int, int]:
        """Total closed-interruption minutes per order, for the KPI
        repository's net-work-time queries. Orders with no interruptions
        are absent from the result (callers treat a missing key as 0)."""
        ...
