"""
The kinds of extra cost a supplier charges beside the line prices, shared by
orders and by the offers of a quote request so a cost carries over unchanged
when an offer is awarded. Every amount is net and stored as a positive number
of cents; a discount is the one kind that is subtracted from the total.
"""

from enum import unique

from src.shared_kernel.domain.value_objects.value_enum import StrValueEnum


@unique
class ExtraCostKind(StrValueEnum):
    SHIPPING = "shipping"
    PACKAGING = "packaging"
    SMALL_ORDER_SURCHARGE = "small_order_surcharge"
    MATERIAL_SURCHARGE = "material_surcharge"
    SETUP = "setup"
    CERTIFICATE = "certificate"
    EXPRESS_SURCHARGE = "express_surcharge"
    CUSTOMS = "customs"
    DISCOUNT = "discount"
    OTHER = "other"

    @property
    def subtracts(self) -> bool:
        """Whether the amount lowers the total instead of adding to it."""
        return self is ExtraCostKind.DISCOUNT

    @property
    def needs_label(self) -> bool:
        """Whether the kind says too little on its own, so the cost needs a
        label that says what it is."""
        return self is ExtraCostKind.OTHER
