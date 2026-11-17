"""
Step "role" for MadeItemProcess / LotStep routing steps: a step is either
FABRICATION (tied to a FabricationMethod/machine) or INSPECTION (a QA
checkpoint with no machine behind it, tied to an InspectionMethod from the
catalogue instead; see src/modules/catalogue/domain/entities/inspection_method.py).
FABRICATION-role steps carry fabrication_method_id; INSPECTION-role steps
carry inspection_method_id; never both. See made_item_rules.
assert_valid_step_role / lot_rules.assert_valid_step_role for the
invariants tying role, fabrication_method_id and inspection_method_id
together (mirrored by DB CHECK constraints on made_item_process_table /
lot_step_table).
"""

from enum import Enum
from enum import unique


@unique
class StepRole(str, Enum):
    FABRICATION = "fabrication"
    INSPECTION = "inspection"

    @classmethod
    def default(cls) -> "StepRole":
        return cls.FABRICATION
