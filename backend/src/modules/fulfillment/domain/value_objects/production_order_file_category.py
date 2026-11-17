"""Evidence file categories for ProductionOrder completion and QA
recording."""

from enum import Enum
from enum import unique


@unique
class ProductionOrderFileCategory(str, Enum):
    """Evidence files attached to a production order completion. A
    completion whose inspection method requires evidence needs at least one
    such file before it can be recorded."""

    MEASUREMENT_REPORT = "measurement_report"  # multiple, e.g. a CMM report PDF or photo

    @classmethod
    def singletons(cls) -> set["ProductionOrderFileCategory"]:
        return set()

    def is_singleton(self) -> bool:
        return self in self.singletons()
