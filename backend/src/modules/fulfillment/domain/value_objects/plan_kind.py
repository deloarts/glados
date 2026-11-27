"""What a recorded production plan is.

BASELINE is the nightly snapshot of the active scheduler's dates for the
committed horizon, the reference daily adherence is measured against. Later
kinds record drafts and commitments. Stored as a plain string column.
"""

from enum import unique

from src.shared_kernel.domain.value_objects.value_enum import StrValueEnum


@unique
class PlanKind(StrValueEnum):
    """Kind of a ProductionPlan."""

    BASELINE = "baseline"


@unique
class PlanStatus(StrValueEnum):
    """Where a ProductionPlan stands. A baseline is recorded once and never
    changes afterwards."""

    RECORDED = "recorded"


@unique
class SchedulerMode(StrValueEnum):
    """Which scheduler dated the orders a plan records. The current one is
    the forward walk with Auto-Plan."""

    CURRENT = "current"
