"""How an interruption of a production order was closed.

RESUME marks a pause that ended because work went on: the order's own resume
or the resume of its lot's hold. CANCEL and CUT mark a pause that ended
because the order left work for good, by a cancel or by a cut back to the
pieces it already processed (a forced lot completion or a piece
disposition). Both stamp `resumed_at`, but no work follows them, so a reader
of the booked work time must not treat them as a resume. Rows closed before
this field existed have none.
"""

from enum import unique

from src.shared_kernel.domain.value_objects.value_enum import StrValueEnum


@unique
class InterruptionEndedBy(StrValueEnum):
    """What closed a ProductionOrderInterruption."""

    RESUME = "resume"
    CANCEL = "cancel"
    CUT = "cut"
