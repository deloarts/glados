"""
Shared wiring for the inspection method read use cases. See
src/modules/catalogue/application/services/labeled_entity_crud.py for the shared logic.
"""

from src.modules.catalogue.application.services.labeled_entity_crud import LabeledEntitySpec
from src.modules.catalogue.domain.entities.inspection_method import InspectionMethod
from src.modules.catalogue.domain.errors import InspectionMethodNotFoundError
from src.modules.catalogue.domain.policies.inspection_method_rules import InspectionMethodRules

SPEC = LabeledEntitySpec(
    entity_cls=InspectionMethod,
    rules=InspectionMethodRules,
    not_found_error=InspectionMethodNotFoundError,
    label="inspection method",
    label_indefinite="An inspection method",
)
