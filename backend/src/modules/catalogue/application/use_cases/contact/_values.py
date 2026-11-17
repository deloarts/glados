"""
The value checks the contact create and update share: trimmed text, the
single organisation, which must exist, and the supplier mail flags.
"""

from src.modules.catalogue.domain.errors import ContactOrganisationInvalidError
from src.modules.catalogue.domain.services.contact_rules import ContactRules
from src.modules.catalogue.ports.outbound.repositories.customer_repository import (
    ICustomerRepository,
)
from src.modules.catalogue.ports.outbound.repositories.supplier_repository import (
    ISupplierRepository,
)
from src.modules.platform.domain.exceptions import InvalidInputError


def optional_text(value: str | None) -> str | None:
    """Trimmed text, or None for a blank one."""
    if value is None:
        return None
    trimmed = value.strip()
    return trimmed or None


def required_name(value: str) -> str:
    name = value.strip()
    if not name:
        raise InvalidInputError("A contact needs a name.")
    return name


async def assert_valid_organisation(
    customers: ICustomerRepository,
    suppliers: ISupplierRepository,
    *,
    customer_id: int | None,
    supplier_id: int | None,
    receives_request_mails: bool,
    receives_order_mails: bool,
) -> None:
    ContactRules.assert_valid_organisation(customer_id, supplier_id)
    ContactRules.assert_valid_mail_flags(supplier_id, receives_request_mails, receives_order_mails)
    if customer_id is not None and await customers.get_by_id(customer_id) is None:
        raise ContactOrganisationInvalidError(f"Customer #{customer_id} not found.")
    if supplier_id is not None and await suppliers.get_by_id(supplier_id) is None:
        raise ContactOrganisationInvalidError(f"Supplier #{supplier_id} not found.")
