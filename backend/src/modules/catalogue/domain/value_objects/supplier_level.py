"""
Supplier quality/preference tier: A/B/C ranking, stored on bought-item
supplier links.
"""

from enum import unique

from src.shared_kernel.domain.value_objects.value_enum import StrValueEnum


@unique
class SupplierLevel(StrValueEnum):
    """Supplier quality/preference tier."""

    A = "A"
    B = "B"
    C = "C"

    @classmethod
    def default(cls) -> "SupplierLevel":
        return cls.B
