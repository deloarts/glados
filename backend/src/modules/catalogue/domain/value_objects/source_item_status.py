"""
Status enum for the SourceItem catalogue aggregate.
"""

from enum import Enum
from enum import unique


@unique
class SourceItemCatalogueStatus(str, Enum):
    """Status of a SourceItem catalogue entry."""

    ACTIVE = "active"
    INACTIVE = "inactive"
    REPLACED = "replaced"

    @classmethod
    def default(cls) -> "SourceItemCatalogueStatus":
        return cls.ACTIVE
