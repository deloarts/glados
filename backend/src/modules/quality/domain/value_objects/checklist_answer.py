"""
The answers a checklist item can get and the overall verdict of a
checklist. "No" and "defect" are findings. The verdict is failed as soon as
one finding exists, even while items are still unanswered, so a finding is
never hidden behind an open checklist.
"""

from enum import Enum
from enum import unique

from src.shared_kernel.domain.value_objects.value_enum import StrValueEnum


@unique
class ChecklistAnswer(StrValueEnum):
    NA = "na"
    YES = "yes"
    NO = "no"
    DEFECT = "defect"


FINDING_ANSWERS: frozenset[str] = frozenset(
    {ChecklistAnswer.NO.value, ChecklistAnswer.DEFECT.value}
)


@unique
class ChecklistVerdict(str, Enum):
    OPEN = "open"
    PASSED = "passed"
    FAILED = "failed"
