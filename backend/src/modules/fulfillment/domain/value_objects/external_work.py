"""The vocabulary of the procurement list of external work: where a position
stands with its supplier and why it needs attention."""

from src.shared_kernel.domain.value_objects.value_enum import StrValueEnum


class ExternalWorkStage(StrValueEnum):
    """Where a position of external work stands with its supplier, as the
    procurement list filters it. Pieces handed over put it at the supplier
    until some come back."""

    UNASSIGNED = "unassigned"
    PENDING = "pending"
    REQUESTED = "requested"
    ORDERED = "ordered"
    AT_SUPPLIER = "at_supplier"
    PARTIALLY_BACK = "partially_back"


class ExternalWorkAlert(StrValueEnum):
    """Why a position of external work needs attention in the procurement
    list. NOT_READY_IN_TIME and OVERDUE are critical, NO_TARGET_DATE only
    explains a missing latest pickup."""

    NOT_READY_IN_TIME = "not_ready_in_time"
    OVERDUE = "overdue"
    NO_TARGET_DATE = "no_target_date"
