"""
Concrete implementation of ISourceItemTypeRepository, a thin subclass of the
shared labeled catalogue repository.
"""

from typing import Any

from sqlalchemy.orm.interfaces import ORMOption

from src.modules.catalogue.adapters.outbound.persistence.mappers.catalogue_mappers import (
    source_item_type_load_options,
)
from src.modules.catalogue.adapters.outbound.persistence.mappers.catalogue_mappers import (
    source_item_type_orm_to_entity,
)
from src.modules.catalogue.adapters.outbound.persistence.models.source_item_type_model import (
    SourceItemTypeOrmModel,
)
from src.modules.catalogue.adapters.outbound.persistence.repositories.labeled_catalogue_repository import (
    LabeledCatalogueRepositoryBase,
)
from src.modules.catalogue.domain.entities.source_item_type import SourceItemType
from src.modules.catalogue.ports.outbound.repositories.source_item_type_repository import (
    ISourceItemTypeRepository,
)


class SqlAlchemySourceItemTypeRepository(
    LabeledCatalogueRepositoryBase[SourceItemType], ISourceItemTypeRepository
):
    """Implements ISourceItemTypeRepository."""

    _model = SourceItemTypeOrmModel

    def _load_options(self) -> tuple[ORMOption, ...]:
        return source_item_type_load_options()

    def _orm_to_entity(self, orm: SourceItemTypeOrmModel) -> SourceItemType:
        return source_item_type_orm_to_entity(orm)

    def _entity_to_dict(self, entity: SourceItemType) -> dict[str, Any]:
        return {
            "created": entity.created,
            "changed": entity.changed,
            "changes": entity.changes,
            "archived": entity.archived,
            "sort_order": entity.sort_order,
            "name": entity.name.as_dict(),
            "label_color": entity.label_color,
            "label_font_color": entity.label_font_color,
            "description": entity.description.as_dict(),
            "creator_id": entity.creator_id,
        }
