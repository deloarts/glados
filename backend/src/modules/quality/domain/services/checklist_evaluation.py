"""
Counts and verdict of a checklist, computed from its answers and the number
of items its type had when it was saved. The backend never sees the item
list itself, which lives in the frontend, so the item count comes with every
save; answers can only shrink the open count, never exceed the total.
No I/O.
"""

from dataclasses import dataclass

from src.modules.quality.domain.errors import ChecklistInvalidAnswersError
from src.modules.quality.domain.value_objects.checklist_answer import FINDING_ANSWERS
from src.modules.quality.domain.value_objects.checklist_answer import ChecklistAnswer
from src.modules.quality.domain.value_objects.checklist_answer import ChecklistVerdict

_ANSWERS = frozenset(ChecklistAnswer.values())


@dataclass(frozen=True)
class ChecklistEvaluation:
    answered_count: int
    finding_count: int
    verdict: ChecklistVerdict


def evaluate(answers: dict[str, str], item_count: int) -> ChecklistEvaluation:
    """Raises ChecklistInvalidAnswersError for an unknown answer value or for
    more answers than the checklist has items."""
    invalid = sorted(key for key, value in answers.items() if value not in _ANSWERS)
    if invalid:
        raise ChecklistInvalidAnswersError(
            f"Unknown answer for item(s) {invalid[:5]}; allowed are {sorted(_ANSWERS)}."
        )
    if len(answers) > item_count:
        raise ChecklistInvalidAnswersError(
            f"{len(answers)} answers for a checklist of {item_count} items."
        )
    findings = sum(1 for value in answers.values() if value in FINDING_ANSWERS)
    if findings > 0:
        verdict = ChecklistVerdict.FAILED
    elif len(answers) < item_count:
        verdict = ChecklistVerdict.OPEN
    else:
        verdict = ChecklistVerdict.PASSED
    return ChecklistEvaluation(answered_count=len(answers), finding_count=findings, verdict=verdict)


def findings_without_remark(answers: dict[str, str], remarks: dict[str, str]) -> list[str]:
    """Item ids answered "no" or "defect" that carry no remark, in key order."""
    return sorted(
        key
        for key, value in answers.items()
        if value in FINDING_ANSWERS and not remarks.get(key, "").strip()
    )
