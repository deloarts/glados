"""
The kind of organisation a contact belongs to.
"""

from enum import unique

from src.shared_kernel.domain.value_objects.value_enum import StrValueEnum


@unique
class ContactOrganisationKind(StrValueEnum):
    """A contact belongs to a customer, to a supplier, or to neither."""

    CUSTOMER = "customer"
    SUPPLIER = "supplier"
