"""
Archives an article group via the shared labeled-entity CRUD service.
"""

from src.modules.catalogue.application.dto.article_group_dto import ArticleGroupResult
from src.modules.catalogue.application.mappers.article_group_mapper import ArticleGroupMapper
from src.modules.catalogue.application.services.labeled_entity_crud import archive_labeled_entity
from src.modules.catalogue.application.use_cases.article_group._spec import SPEC
from src.modules.catalogue.ports.outbound.repositories.article_group_repository import (
    IArticleGroupRepository,
)
from src.modules.platform.domain.entities.user import User
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork


class ArchiveArticleGroup:
    def __init__(
        self,
        article_group_repo: IArticleGroupRepository,
        *,
        uow: IUnitOfWork,
    ) -> None:
        self._article_groups = article_group_repo
        self._uow = uow

    async def execute(self, actor: User, article_group_id: int) -> ArticleGroupResult:
        saved = await archive_labeled_entity(SPEC, self._article_groups, actor, article_group_id)
        await self._uow.commit()
        return ArticleGroupMapper.to_result(saved)
