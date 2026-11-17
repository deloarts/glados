"""What a planning exception reports, the shortfalls and delays a planner
acts on (production_lot/get_planning_exceptions.py)."""

from enum import unique

from src.shared_kernel.domain.value_objects.value_enum import StrValueEnum


@unique
class PlanningExceptionKind(StrValueEnum):
    """LOST_AT_RECEIPT and CLOSED_SHORT: a bought or raw material demand has
    a rest open again because its order line lost pieces or was closed
    short. LOT_ENDED_SHORT: a made demand's lot was force-completed below
    what the demand needs. MATERIAL_SHORT: a live lot's raw material is
    partly unallocated or waits on a line without a delivery date, so its
    first step cannot be planned in full. LATE: a live lot is past its
    target date or planned to end after it."""

    LOST_AT_RECEIPT = "lost_at_receipt"
    CLOSED_SHORT = "closed_short"
    LOT_ENDED_SHORT = "lot_ended_short"
    MATERIAL_SHORT = "material_short"
    LATE = "late"
