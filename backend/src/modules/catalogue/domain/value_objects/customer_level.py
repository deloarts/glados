"""
Customer priority tier: an A/B/C ranking the office sets on each customer.
"""

from enum import unique

from src.shared_kernel.domain.value_objects.value_enum import StrValueEnum


@unique
class CustomerLevel(StrValueEnum):
    """Customer priority tier."""

    A = "A"
    B = "B"
    C = "C"

    @classmethod
    def default(cls) -> "CustomerLevel":
        return cls.B
