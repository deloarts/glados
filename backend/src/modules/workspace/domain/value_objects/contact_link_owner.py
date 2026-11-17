"""
What a contact link belongs to.
"""

from enum import unique

from src.shared_kernel.domain.value_objects.value_enum import StrValueEnum


@unique
class ContactLinkOwner(StrValueEnum):
    PRODUCT = "product"
    PROJECT = "project"
