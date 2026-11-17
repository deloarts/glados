"""
Concrete implementation of IArticleGroupRepository, a subclass of the shared
labeled catalogue repository that adds the lookup of several groups by id.
"""

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm.interfaces import ORMOption

from src.modules.catalogue.adapters.outbound.persistence.mappers.catalogue_mappers import (
    article_group_load_options,
)
from src.modules.catalogue.adapters.outbound.persistence.mappers.catalogue_mappers import (
    article_group_orm_to_entity,
)
from src.modules.catalogue.adapters.outbound.persistence.models.article_group_model import (
    ArticleGroupOrmModel,
)
from src.modules.catalogue.adapters.outbound.persistence.repositories.labeled_catalogue_repository import (
    LabeledCatalogueRepositoryBase,
)
from src.modules.catalogue.domain.entities.article_group import ArticleGroup
from src.modules.catalogue.ports.outbound.repositories.article_group_repository import (
    IArticleGroupRepository,
)


class SqlAlchemyArticleGroupRepository(
    LabeledCatalogueRepositoryBase[ArticleGroup], IArticleGroupRepository
):
    """Implements IArticleGroupRepository."""

    _model = ArticleGroupOrmModel

    def _load_options(self) -> tuple[ORMOption, ...]:
        return article_group_load_options()

    def _orm_to_entity(self, orm: ArticleGroupOrmModel) -> ArticleGroup:
        return article_group_orm_to_entity(orm)

    def _entity_to_dict(self, entity: ArticleGroup) -> dict[str, Any]:
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

    async def get_by_ids(self, ids: list[int]) -> list[ArticleGroup]:
        if not ids:
            return []
        rows = (
            await self._db.scalars(
                select(ArticleGroupOrmModel)
                .where(ArticleGroupOrmModel.id.in_(ids))
                .options(*article_group_load_options())
            )
        ).all()
        return [article_group_orm_to_entity(r) for r in rows]
