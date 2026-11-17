"""Document categories for procurement orders: proposals, order
confirmations, delivery notes, invoices, pictures, and generic documents.
Every category accumulates, so an order may carry several invoices."""

from enum import Enum
from enum import unique


@unique
class OrderFileCategory(str, Enum):
    PROPOSAL = "proposal"  # quotation
    ORDER_CONFIRMATION = "order_confirmation"  # order confirmation
    DELIVERY_NOTE = "delivery_note"  # delivery note
    INVOICE = "invoice"
    GENERAL = "general"  # generic document
    PICTURE = "picture"  # photo documenting the order

    @classmethod
    def singletons(cls) -> set["OrderFileCategory"]:
        return set()

    def is_singleton(self) -> bool:
        return self in self.singletons()
