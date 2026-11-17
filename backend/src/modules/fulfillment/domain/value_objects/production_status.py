"""
UrgencyClass backs ProductionLot.priority. It is a free classification
and sort key, not a lifecycle status.

ProductionOrderStatus tracks ProductionOrder queueing/execution;
ComplexityClass backs ManufacturingAssessment data collection. Real
automated time estimation (a statistical/ML TimeEstimationPort) doesn't
exist yet; ManufacturingAssessment capture starts here deliberately,
ahead of any estimation model, so a training dataset is ready once one
is built.
"""

from enum import unique

from src.shared_kernel.domain.value_objects.value_enum import StrValueEnum


@unique
class UrgencyClass(StrValueEnum):
    """Priority classification used as the primary sort key for planning."""

    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"

    @classmethod
    def default(cls) -> "UrgencyClass":
        return cls.NORMAL


@unique
class ProductionOrderStatus(StrValueEnum):
    """Status of a ProductionOrder queued on a ProductionMachine."""

    QUEUED = "queued"
    IN_PROGRESS = "in_progress"
    PAUSED = "paused"
    COMPLETED = "completed"
    CANCELED = "canceled"

    @classmethod
    def default(cls) -> "ProductionOrderStatus":
        return cls.QUEUED


# The statuses a production order never leaves, and the ones it can still be
# worked or rescheduled in. Filters and guards on finished orders read these.
TERMINAL_PRODUCTION_ORDER_STATUSES: frozenset[str] = frozenset(
    {ProductionOrderStatus.COMPLETED, ProductionOrderStatus.CANCELED}
)
ACTIVE_PRODUCTION_ORDER_STATUSES: frozenset[str] = frozenset(
    {
        ProductionOrderStatus.QUEUED,
        ProductionOrderStatus.IN_PROGRESS,
        ProductionOrderStatus.PAUSED,
    }
)


@unique
class ComplexityClass(StrValueEnum):
    """Operator-assessed complexity of a completed production order.

    Free classification for the AI-time-estimation training dataset, no
    lifecycle, mirrors UrgencyClass's shape.
    """

    LOW = "low"
    NORMAL = "normal"
    VERY = "very"

    @classmethod
    def default(cls) -> "ComplexityClass":
        return cls.NORMAL
