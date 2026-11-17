"""
Converts between ArticleGroup domain entity and DTOs.
"""

from src.modules.catalogue.application.dto.article_group_dto import ArticleGroupResult
from src.modules.catalogue.domain.entities.article_group import ArticleGroup
from src.modules.platform.application.mappers.user_mapper import UserMapper


class ArticleGroupMapper:
    @staticmethod
    def to_result(entity: ArticleGroup) -> ArticleGroupResult:
        return ArticleGroupResult(
            id=entity.id,
            public_id=entity.public_id,
            created=entity.created,
            changed=entity.changed,
            sort_order=entity.sort_order,
            archived=entity.archived,
            name=entity.name.as_dict(),
            label_color=entity.label_color,
            label_font_color=entity.label_font_color,
            description=entity.description.as_dict(),
            creator_id=entity.creator_id,
            creator=UserMapper.to_public_result(entity.creator) if entity.creator else None,
            changed_by_id=entity.changed_by_id,
            changed_by=UserMapper.to_public_result(entity.changed_by)
            if entity.changed_by
            else None,
        )
