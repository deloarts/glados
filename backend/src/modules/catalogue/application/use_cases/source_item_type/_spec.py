"""
Shared wiring for the source item type CRUD use cases. See
src/modules/catalogue/application/services/labeled_entity_crud.py for the shared logic.
"""

from src.modules.catalogue.application.services.labeled_entity_crud import LabeledEntitySpec
from src.modules.catalogue.domain.entities.source_item_type import SourceItemType
from src.modules.catalogue.domain.errors import SourceItemTypeNotFoundError
from src.modules.catalogue.domain.services.source_item_type_rules import SourceItemTypeRules

SPEC = LabeledEntitySpec(
    entity_cls=SourceItemType,
    rules=SourceItemTypeRules,
    not_found_error=SourceItemTypeNotFoundError,
    label="source item type",
    label_indefinite="A source item type",
)
