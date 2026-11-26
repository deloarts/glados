"""
Concrete implementation of IInspectionMethodRepository, a subclass of the shared
labeled catalogue repository that adds the inspection method columns.
"""

from typing import Any

from sqlalchemy.orm.interfaces import ORMOption

from src.modules.catalogue.adapters.outbound.persistence.mappers.catalogue_mappers import (
    inspection_method_load_options,
)
from src.modules.catalogue.adapters.outbound.persistence.mappers.catalogue_mappers import (
    inspection_method_orm_to_entity,
)
from src.modules.catalogue.adapters.outbound.persistence.models.inspection_method_model import (
    InspectionMethodOrmModel,
)
from src.modules.catalogue.adapters.outbound.persistence.repositories.labeled_catalogue_repository import (
    LabeledCatalogueRepositoryBase,
)
from src.modules.catalogue.domain.entities.inspection_method import InspectionMethod
from src.modules.catalogue.ports.outbound.repositories.inspection_method_repository import (
    IInspectionMethodRepository,
)


class SqlAlchemyInspectionMethodRepository(
    LabeledCatalogueRepositoryBase[InspectionMethod], IInspectionMethodRepository
):
    """Implements IInspectionMethodRepository."""

    _model = InspectionMethodOrmModel

    def _load_options(self) -> tuple[ORMOption, ...]:
        return inspection_method_load_options()

    def _orm_to_entity(self, orm: InspectionMethodOrmModel) -> InspectionMethod:
        return inspection_method_orm_to_entity(orm)

    def _entity_to_dict(self, entity: InspectionMethod) -> dict[str, Any]:
        return {
            "created": entity.created,
            "changed": entity.changed,
            "changes": entity.changes,
            "name": entity.name.as_dict(),
            "label_color": entity.label_color,
            "label_font_color": entity.label_font_color,
            "description": entity.description.as_dict(),
            "creator_id": entity.creator_id,
            "default_setup_minutes": entity.default_setup_minutes,
            "default_minutes_per_piece": entity.default_minutes_per_piece,
            "wait_after_minutes": entity.wait_after_minutes,
            "requires_evidence": entity.requires_evidence,
            "archived": entity.archived,
            "sort_order": entity.sort_order,
            # default_machine_name is NOT here since it's derived (mappers.py),
            # never a column to write back.
            "default_machine_id": entity.default_machine_id,
        }
