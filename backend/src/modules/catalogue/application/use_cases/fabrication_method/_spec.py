"""
Shared wiring for the fabrication method CRUD use cases. See
src/modules/catalogue/application/services/labeled_entity_crud.py for the shared logic.
"""

from src.modules.catalogue.application.services.labeled_entity_crud import LabeledEntitySpec
from src.modules.catalogue.domain.entities.fabrication_method import FabricationMethod
from src.modules.catalogue.domain.errors import FabricationMethodNotFoundError
from src.modules.catalogue.domain.services.fabrication_method_rules import FabricationMethodRules

SPEC = LabeledEntitySpec(
    entity_cls=FabricationMethod,
    rules=FabricationMethodRules,
    not_found_error=FabricationMethodNotFoundError,
    label="fabrication method",
    label_indefinite="A fabrication method",
)
