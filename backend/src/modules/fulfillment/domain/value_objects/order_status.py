"""
Status enums for the generic Order/OrderItem vertical.
"""

from enum import Enum
from enum import unique

from src.shared_kernel.domain.value_objects.value_enum import StrValueEnum


@unique
class OrderStatus(StrValueEnum):
    """Status of an Order."""

    DRAFT = "draft"
    REQUESTED = "requested"
    PARTIALLY_ORDERED = "partially_ordered"
    ORDERED = "ordered"
    PARTIALLY_DELIVERED = "partially_delivered"
    DELIVERED = "delivered"
    CANCELED = "canceled"

    @classmethod
    def default(cls) -> "OrderStatus":
        return cls.DRAFT


@unique
class OrderItemStatus(StrValueEnum):
    """Status of a single line item within an Order."""

    PENDING = "pending"  # added to order, not yet confirmed as ordered
    REQUESTED = "requested"  # buyer sent a request, negotiating price with supplier
    ORDERED = "ordered"
    PARTIALLY_DELIVERED = "partially_delivered"
    DELIVERED = "delivered"
    CANCELED = "canceled"

    @classmethod
    def default(cls) -> "OrderItemStatus":
        return cls.PENDING


@unique
class OrderLineType(str, Enum):
    """What kind of line an OrderItem represents."""

    BOUGHT = "BOUGHT"
    MADE = "MADE"
    SOURCE = "SOURCE"
    VIRTUAL = "VIRTUAL"

    @classmethod
    def default(cls) -> "OrderLineType":
        return cls.BOUGHT
