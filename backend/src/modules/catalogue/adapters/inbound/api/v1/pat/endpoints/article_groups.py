"""
PAT surface, read-only article group access.
"""

from datetime import tzinfo

from fastapi import Depends
from fastapi.routing import APIRouter

from src.modules.catalogue.adapters.inbound.api.deps.items import get_article_group_use_case
from src.modules.catalogue.adapters.inbound.api.deps.items import get_article_groups_use_case
from src.modules.catalogue.adapters.inbound.api.schemas.article_group_schema import (
    ArticleGroupFilterParams,
)
from src.modules.catalogue.adapters.inbound.api.schemas.article_group_schema import (
    ArticleGroupResponse,
)
from src.modules.catalogue.application.use_cases.article_group.get_article_group import (
    GetArticleGroup,
)
from src.modules.catalogue.application.use_cases.article_group.get_article_group import (
    GetArticleGroups,
)
from src.modules.platform.adapters.inbound.api.auth_deps import get_current_user_pat
from src.modules.platform.adapters.inbound.api.deps.misc import get_tenant_zone
from src.modules.platform.adapters.inbound.api.schemas.pagination_schema import PageResponse
from src.modules.platform.domain.entities.user import User
from src.modules.platform.infrastructure.label_languages import label_languages

router = APIRouter()


@router.get("/", response_model=PageResponse[ArticleGroupResponse])
async def read_article_groups(
    params: ArticleGroupFilterParams = Depends(),
    _: User = Depends(get_current_user_pat),
    zone: tzinfo = Depends(get_tenant_zone),
    use_case: GetArticleGroups = Depends(get_article_groups_use_case),
) -> PageResponse[ArticleGroupResponse]:
    result = await use_case.execute(params.to_dto(zone, label_languages()))
    return PageResponse.from_result(result, params, item_model=ArticleGroupResponse)


@router.get("/{article_group_id}", response_model=ArticleGroupResponse)
async def read_article_group(
    article_group_id: int,
    _: User = Depends(get_current_user_pat),
    use_case: GetArticleGroup = Depends(get_article_group_use_case),
) -> ArticleGroupResponse:
    result = await use_case.execute(article_group_id=article_group_id)
    return ArticleGroupResponse.model_validate(result.model_dump())
