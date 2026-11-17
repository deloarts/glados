"""
Shared wiring for the product family CRUD use cases. See
src/modules/catalogue/application/services/named_entity_crud.py for the shared logic.
"""

from src.modules.catalogue.application.services.named_entity_crud import NamedEntitySpec
from src.modules.catalogue.domain.entities.product_family import ProductFamily
from src.modules.catalogue.domain.errors import ProductFamilyAlreadyExistsError
from src.modules.catalogue.domain.errors import ProductFamilyNotFoundError
from src.modules.catalogue.domain.services.product_family_rules import ProductFamilyRules

SPEC = NamedEntitySpec(
    entity_cls=ProductFamily,
    rules=ProductFamilyRules,
    not_found_error=ProductFamilyNotFoundError,
    already_exists_error=ProductFamilyAlreadyExistsError,
    label="product family",
    label_indefinite="A product family",
)
