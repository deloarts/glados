"""
Creates a new article group via the shared labeled-entity CRUD service.
"""

from src.modules.catalogue.application.dto.article_group_dto import ArticleGroupResult
from src.modules.catalogue.application.dto.article_group_dto import CreateArticleGroupCommand
from src.modules.catalogue.application.mappers.article_group_mapper import ArticleGroupMapper
from src.modules.catalogue.application.services.labeled_entity_crud import create_labeled_entity
from src.modules.catalogue.application.use_cases.article_group._spec import SPEC
from src.modules.catalogue.ports.outbound.repositories.article_group_repository import (
    IArticleGroupRepository,
)
from src.modules.platform.domain.entities.user import User
from src.modules.platform.ports.outbound.platform_settings_repository import (
    IPlatformSettingsRepository,
)
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork


class CreateArticleGroup:
    def __init__(
        self,
        article_group_repo: IArticleGroupRepository,
        *,
        settings: IPlatformSettingsRepository,
        uow: IUnitOfWork,
    ) -> None:
        self._article_groups = article_group_repo
        self._settings = settings
        self._uow = uow

    async def execute(self, actor: User, cmd: CreateArticleGroupCommand) -> ArticleGroupResult:
        saved = await create_labeled_entity(SPEC, self._article_groups, self._settings, actor, cmd)
        await self._uow.commit()
        return ArticleGroupMapper.to_result(saved)
