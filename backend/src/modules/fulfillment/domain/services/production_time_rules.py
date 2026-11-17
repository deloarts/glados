"""
Pure functions turning a production order's actuals and interruption
history into a net work time, the KPI backend's building block for
utilization and estimate-accuracy calculations, and into the moment the
order last went back to work, where the scheduler anchors a running order.
Deliberately knows nothing about repositories or persistence, only plain
values and domain entities already loaded by the caller.
"""

from collections.abc import Sequence
from datetime import datetime

from src.modules.fulfillment.domain.entities.production_order_interruption import (
    ProductionOrderInterruption,
)


def net_work_minutes(
    actual_start: datetime | None,
    actual_end: datetime | None,
    interruptions: Sequence[ProductionOrderInterruption],
) -> int | None:
    """Minutes actually worked on an order: the elapsed time between
    actual_start and actual_end, minus every closed interruption's own
    duration. None until the order has both an actual start and an
    actual end (in progress or never started orders have no net work
    time yet). An interruption still open at actual_end (should not
    happen in practice, resuming always closes the open one before an
    order can complete) is excluded from the subtraction rather than
    guessed at, so a stray open row never produces a negative or
    otherwise meaningless result. Clamped at 0 for the same reason."""
    if actual_start is None or actual_end is None:
        return None
    elapsed_seconds = (actual_end - actual_start).total_seconds()
    interruption_seconds = sum(
        (i.resumed_at - i.paused_at).total_seconds()
        for i in interruptions
        if i.resumed_at is not None
    )
    minutes = round((elapsed_seconds - interruption_seconds) / 60)
    return max(minutes, 0)


def last_resumed_at(interruptions: Sequence[ProductionOrderInterruption]) -> datetime | None:
    """The end of the latest closed interruption, which for a live order is
    the moment it last went back to work. None while no interruption has
    been closed; an open one has no end yet and is skipped."""
    return max((i.resumed_at for i in interruptions if i.resumed_at is not None), default=None)
