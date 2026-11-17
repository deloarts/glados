"""
Status enums for the BoughtItem catalogue/demand aggregates.
Order/OrderItem status enums live in order_status.py.
"""

from enum import Enum
from enum import unique

from src.shared_kernel.domain.value_objects.value_enum import StrValueEnum


@unique
class BoughtItemCatalogueStatus(str, Enum):
    """Status of a BoughtItem catalogue entry."""

    ACTIVE = "active"
    INACTIVE = "inactive"
    REPLACED = "replaced"

    @classmethod
    def default(cls) -> "BoughtItemCatalogueStatus":
        return cls.ACTIVE


@unique
class BoughtItemDemandStatus(StrValueEnum):
    """Status of a BoughtItemDemandItem (project need)."""

    OPEN = "open"
    ALLOCATED = "allocated"  # at least one allocation exists
    ORDERED = "ordered"  # all linked order items have been ordered
    FULFILLED = "fulfilled"  # all quantity covered and delivered
    CANCELED = "canceled"

    @classmethod
    def default(cls) -> "BoughtItemDemandStatus":
        return cls.OPEN


@unique
class AllocationSource(str, Enum):
    """Where a BoughtItemDemandAllocation's quantity comes from."""

    ORDER = "order"  # linked to an OrderItem, awaiting delivery
    STOCK = "stock"  # satisfied immediately from on-hand stock, no order_item_id

    @classmethod
    def default(cls) -> "AllocationSource":
        return cls.ORDER
