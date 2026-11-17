"""
Status enums for the MadeItem catalogue/demand aggregates.
"""

from enum import Enum
from enum import unique

from src.shared_kernel.domain.value_objects.value_enum import StrValueEnum


@unique
class MadeItemCatalogueStatus(str, Enum):
    """Status of a MadeItem catalogue entry."""

    ACTIVE = "active"
    INACTIVE = "inactive"
    REPLACED = "replaced"

    @classmethod
    def default(cls) -> "MadeItemCatalogueStatus":
        return cls.ACTIVE


@unique
class MadeItemDemandStatus(StrValueEnum):
    """Status of a MadeItemDemandItem (project need)."""

    OPEN = "open"
    ALLOCATED = "allocated"  # at least one allocation exists
    ORDERED = "ordered"  # the covering lot has started being planned (beyond DRAFT)
    FULFILLED = "fulfilled"  # all quantity covered and delivered
    CANCELED = "canceled"

    @classmethod
    def default(cls) -> "MadeItemDemandStatus":
        return cls.OPEN


@unique
class MadeItemAllocationSource(str, Enum):
    """Where a MadeItemDemandAllocation's quantity comes from."""

    LOT = "lot"  # linked to a ProductionLot, awaiting completion
    STOCK = "stock"  # satisfied immediately from on-hand stock, no lot_id

    @classmethod
    def default(cls) -> "MadeItemAllocationSource":
        return cls.LOT
