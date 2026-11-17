"""
Concrete implementation of IProductFamilyRepository, a subclass of the shared
labeled catalogue repository that adds the lookup of several groups by id.
"""

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm.interfaces import ORMOption

from src.modules.catalogue.adapters.outbound.persistence.models.product_family_model import (
    ProductFamilyOrmModel,
)
from src.modules.catalogue.adapters.outbound.persistence.product_family_mappers import (
    product_family_load_options,
)
from src.modules.catalogue.adapters.outbound.persistence.product_family_mappers import (
    product_family_orm_to_entity,
)
from src.modules.catalogue.adapters.outbound.persistence.repositories.labeled_catalogue_repository import (
    LabeledCatalogueRepositoryBase,
)
from src.modules.catalogue.domain.entities.product_family import ProductFamily
from src.modules.catalogue.ports.outbound.repositories.product_family_repository import (
    IProductFamilyRepository,
)


class SqlAlchemyProductFamilyRepository(
    LabeledCatalogueRepositoryBase[ProductFamily], IProductFamilyRepository
):
    """Implements IProductFamilyRepository."""

    _model = ProductFamilyOrmModel
    _localized = False

    def _load_options(self) -> tuple[ORMOption, ...]:
        return product_family_load_options()

    def _orm_to_entity(self, orm: ProductFamilyOrmModel) -> ProductFamily:
        return product_family_orm_to_entity(orm)

    def _entity_to_dict(self, entity: ProductFamily) -> dict[str, Any]:
        return {
            "created": entity.created,
            "changed": entity.changed,
            "changes": entity.changes,
            "archived": entity.archived,
            "sort_order": entity.sort_order,
            "name": entity.name,
            "label_color": entity.label_color,
            "label_font_color": entity.label_font_color,
            "description": entity.description,
            "creator_id": entity.creator_id,
        }

    async def get_by_ids(self, ids: list[int]) -> list[ProductFamily]:
        if not ids:
            return []
        rows = (
            await self._db.scalars(
                select(ProductFamilyOrmModel)
                .where(ProductFamilyOrmModel.id.in_(ids))
                .options(*product_family_load_options())
            )
        ).all()
        return [product_family_orm_to_entity(r) for r in rows]
