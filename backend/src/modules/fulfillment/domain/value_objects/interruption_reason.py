"""Why an interruption of a production order was opened.

MANUAL marks a pause an operator asked for, and only a manual resume closes
it. LOT_HOLD marks an interruption that belongs to a hold of the order's lot,
and resuming the lot closes it. The reason keeps the two apart, so resuming a
lot never restarts an order an operator paused by hand.
"""

from enum import unique

from src.shared_kernel.domain.value_objects.value_enum import StrValueEnum


@unique
class InterruptionReason(StrValueEnum):
    """Reason of a ProductionOrderInterruption."""

    MANUAL = "manual"
    LOT_HOLD = "lot_hold"

    @classmethod
    def default(cls) -> "InterruptionReason":
        return cls.MANUAL
