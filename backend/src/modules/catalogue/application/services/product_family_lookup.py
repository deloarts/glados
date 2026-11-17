"""
The reference check for a bought item's product family, shared by the
create and update use cases and the spreadsheet import.
"""

from src.modules.catalogue.domain.errors import ProductFamilyNotFoundError
from src.modules.catalogue.ports.outbound.repositories.product_family_repository import (
    IProductFamilyRepository,
)


async def assert_product_family_exists(
    repo: IProductFamilyRepository | None, product_family_id: int | None
) -> None:
    """Raises ProductFamilyNotFoundError when `product_family_id` names no
    product family or an archived one. No family, or no repository (a caller
    that cannot set one), passes."""
    if product_family_id is None or repo is None:
        return
    family = await repo.get_by_id(product_family_id)
    if family is None or family.archived:
        raise ProductFamilyNotFoundError(f"Product family #{product_family_id} not found.")
