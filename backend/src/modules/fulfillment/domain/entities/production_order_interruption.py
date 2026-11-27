"""
One pause and resume cycle on a ProductionOrder. Pausing opens a row with no
resumed_at and resuming closes it; every pause adds a new row, so the history
stays complete for production_time_rules.net_work_minutes. `reason` tells a
manual pause from one caused by a hold of the order's lot, and `ended_by`
tells a resume from a cancel or a cut, which close the row without any work
following it.
"""

from dataclasses import dataclass
from datetime import datetime

from src.modules.fulfillment.domain.value_objects.interruption_ended_by import InterruptionEndedBy
from src.modules.fulfillment.domain.value_objects.interruption_reason import InterruptionReason
from src.modules.fulfillment.domain.value_objects.pause_cause import PauseCause
from src.shared_kernel.domain.entities.base import Entity


@dataclass
class ProductionOrderInterruption(Entity):
    production_order_id: int  # → ProductionOrder
    paused_at: datetime
    resumed_at: datetime | None  # None while the order is still paused
    paused_by_id: int  # → User, who paused the order
    resumed_by_id: int | None  # → User, who resumed it; None while open
    created: datetime
    reason: InterruptionReason = InterruptionReason.MANUAL
    # → User, the operator who paused the work: the member a shared account
    # names, the session user otherwise; None for a lot hold a shared
    # account placed.
    paused_operator_id: int | None = None
    # → User, the operator who went on with the work when the order's own
    # start resumed it; None while open, after a lot resume, a cancel or a
    # cut, and on rows closed before the field existed.
    resumed_operator_id: int | None = None
    # What closed the row; None while open and on rows closed before the
    # field existed.
    ended_by: InterruptionEndedBy | None = None
    # The cause an operator picked for a manual pause; None for a lot hold
    # and for a pause without one.
    pause_cause: PauseCause | None = None
