"""
Status enum for the SourceItemDemandItem aggregate. Mirrors
BoughtItemDemandStatus exactly, a real stored column, derived by the
lifecycle reconciler (domain/services/lifecycle/demand.py), not at read
time.
"""

from enum import Enum
from enum import unique

from src.shared_kernel.domain.value_objects.value_enum import StrValueEnum


@unique
class SourceItemDemandStatus(StrValueEnum):
    OPEN = "open"  # no allocation exists yet
    ALLOCATED = "allocated"  # at least one allocation exists
    ORDERED = "ordered"  # all linked order items have been ordered
    FULFILLED = "fulfilled"  # all quantity covered and delivered
    CANCELED = "canceled"

    @classmethod
    def default(cls) -> "SourceItemDemandStatus":
        return cls.OPEN


@unique
class SourceItemAllocationSource(str, Enum):
    """Where a SourceItemDemandAllocation's quantity comes from."""

    ORDER = "order"  # linked to an OrderItem, awaiting delivery
    STOCK = "stock"  # satisfied immediately from on-hand stock, no order_item_id

    @classmethod
    def default(cls) -> "SourceItemAllocationSource":
        return cls.ORDER
