"""
Retrieves a single article group by ID or lists article groups with pagination via the
shared labeled-entity service.
"""

from src.modules.catalogue.application.dto.article_group_dto import ArticleGroupResult
from src.modules.catalogue.application.mappers.article_group_mapper import ArticleGroupMapper
from src.modules.catalogue.application.services.labeled_entity_crud import get_labeled_entities
from src.modules.catalogue.application.services.labeled_entity_crud import get_labeled_entity
from src.modules.catalogue.application.use_cases.article_group._spec import SPEC
from src.modules.catalogue.ports.outbound.catalogue_queries import ArticleGroupFilterDto
from src.modules.catalogue.ports.outbound.repositories.article_group_repository import (
    IArticleGroupRepository,
)


class PaginatedArticleGroups:
    def __init__(self, total: int, items: list[ArticleGroupResult]):
        self.total = total
        self.items = items


class GetArticleGroup:
    def __init__(self, article_group_repo: IArticleGroupRepository) -> None:
        self._article_groups = article_group_repo

    async def execute(self, article_group_id: int) -> ArticleGroupResult:
        entity = await get_labeled_entity(SPEC, self._article_groups, article_group_id)
        return ArticleGroupMapper.to_result(entity)

    async def changelog(self, article_group_id: int) -> list[str]:
        """The article group's changelog lines; a missing id raises the same
        not-found error as execute."""
        entity = await get_labeled_entity(SPEC, self._article_groups, article_group_id)
        return entity.changes


class GetArticleGroups:
    def __init__(self, article_group_repo: IArticleGroupRepository) -> None:
        self._article_groups = article_group_repo

    async def execute(self, filters: ArticleGroupFilterDto) -> PaginatedArticleGroups:
        total, items = await get_labeled_entities(self._article_groups, filters)
        return PaginatedArticleGroups(
            total=total, items=[ArticleGroupMapper.to_result(i) for i in items]
        )
