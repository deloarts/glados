"""Why an operator paused a production order, picked from a fixed list.

The cause sits next to the free-text reason a pause already takes, so pauses
can be counted by cause without reading prose. It applies only to a manual
pause; a hold of the order's lot has a reason of its own. Stored as a plain
string column and validated at the API boundary, so a later cause needs no
schema change.
"""

from enum import unique

from src.shared_kernel.domain.value_objects.value_enum import StrValueEnum


@unique
class PauseCause(StrValueEnum):
    """The cause of a manual pause of a production order."""

    WAITING_FOR_MATERIAL = "waiting_for_material"
    WAITING_FOR_TOOL = "waiting_for_tool"
    WAITING_FOR_DRAWING = "waiting_for_drawing"
    WAITING_FOR_QA = "waiting_for_qa"
    MACHINE_FAULT = "machine_fault"
    OTHER_WORK = "other_work"
    END_OF_SHIFT = "end_of_shift"
