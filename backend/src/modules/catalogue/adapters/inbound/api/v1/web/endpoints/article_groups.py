"""
Article group endpoints, manages the catalogue grouping/labelling
referenced by bought items.
"""

from datetime import tzinfo

from fastapi import Depends
from fastapi import status
from fastapi.routing import APIRouter

from src.modules.catalogue.adapters.inbound.api.deps.items import get_archive_article_group_use_case
from src.modules.catalogue.adapters.inbound.api.deps.items import get_article_group_use_case
from src.modules.catalogue.adapters.inbound.api.deps.items import get_article_groups_use_case
from src.modules.catalogue.adapters.inbound.api.deps.items import get_create_article_group_use_case
from src.modules.catalogue.adapters.inbound.api.deps.items import get_move_article_group_use_case
from src.modules.catalogue.adapters.inbound.api.deps.items import get_place_article_group_use_case
from src.modules.catalogue.adapters.inbound.api.deps.items import get_restore_article_group_use_case
from src.modules.catalogue.adapters.inbound.api.deps.items import get_update_article_group_use_case
from src.modules.catalogue.adapters.inbound.api.schemas.article_group_schema import (
    ArticleGroupCreateRequest,
)
from src.modules.catalogue.adapters.inbound.api.schemas.article_group_schema import (
    ArticleGroupFilterParams,
)
from src.modules.catalogue.adapters.inbound.api.schemas.article_group_schema import (
    ArticleGroupUpdateRequest,
)
from src.modules.catalogue.adapters.inbound.api.schemas.article_group_schema import (
    ArticleGroupWebResponse,
)
from src.modules.catalogue.application.dto.article_group_dto import CreateArticleGroupCommand
from src.modules.catalogue.application.dto.article_group_dto import UpdateArticleGroupCommand
from src.modules.catalogue.application.use_cases.article_group.archive_article_group import (
    ArchiveArticleGroup,
)
from src.modules.catalogue.application.use_cases.article_group.create_article_group import (
    CreateArticleGroup,
)
from src.modules.catalogue.application.use_cases.article_group.get_article_group import (
    GetArticleGroup,
)
from src.modules.catalogue.application.use_cases.article_group.get_article_group import (
    GetArticleGroups,
)
from src.modules.catalogue.application.use_cases.article_group.move_article_group import (
    MoveArticleGroup,
)
from src.modules.catalogue.application.use_cases.article_group.move_article_group import (
    PlaceArticleGroup,
)
from src.modules.catalogue.application.use_cases.article_group.restore_article_group import (
    RestoreArticleGroup,
)
from src.modules.catalogue.application.use_cases.article_group.update_article_group import (
    UpdateArticleGroup,
)
from src.modules.platform.adapters.inbound.api.auth_deps import get_current_active_user
from src.modules.platform.adapters.inbound.api.deps.misc import get_label_languages
from src.modules.platform.adapters.inbound.api.deps.misc import get_tenant_zone
from src.modules.platform.adapters.inbound.api.schemas.list_move_schema import ListMoveRequest
from src.modules.platform.adapters.inbound.api.schemas.list_move_schema import ListPlaceRequest
from src.modules.platform.adapters.inbound.api.schemas.pagination_schema import PageResponse
from src.modules.platform.domain.entities.user import User

router = APIRouter()


@router.get("/", response_model=PageResponse[ArticleGroupWebResponse])
async def read_article_groups(
    params: ArticleGroupFilterParams = Depends(),
    _: User = Depends(get_current_active_user),
    zone: tzinfo = Depends(get_tenant_zone),
    languages: tuple[str, ...] = Depends(get_label_languages),
    use_case: GetArticleGroups = Depends(get_article_groups_use_case),
) -> PageResponse[ArticleGroupWebResponse]:
    result = await use_case.execute(params.to_dto(zone, languages))
    return PageResponse.from_result(result, params, item_model=ArticleGroupWebResponse)


@router.post("/", response_model=ArticleGroupWebResponse, status_code=status.HTTP_201_CREATED)
async def create_article_group(
    body: ArticleGroupCreateRequest,
    actor: User = Depends(get_current_active_user),
    use_case: CreateArticleGroup = Depends(get_create_article_group_use_case),
) -> ArticleGroupWebResponse:
    cmd = CreateArticleGroupCommand(**body.model_dump())
    result = await use_case.execute(actor=actor, cmd=cmd)
    return ArticleGroupWebResponse.model_validate(result.model_dump())


@router.get("/{article_group_id}", response_model=ArticleGroupWebResponse)
async def read_article_group(
    article_group_id: int,
    _: User = Depends(get_current_active_user),
    use_case: GetArticleGroup = Depends(get_article_group_use_case),
) -> ArticleGroupWebResponse:
    result = await use_case.execute(article_group_id=article_group_id)
    return ArticleGroupWebResponse.model_validate(result.model_dump())


@router.get("/{article_group_id}/changelog", response_model=list[str])
async def read_article_group_changelog(
    article_group_id: int,
    _: User = Depends(get_current_active_user),
    use_case: GetArticleGroup = Depends(get_article_group_use_case),
) -> list[str]:
    return await use_case.changelog(article_group_id)


@router.put("/{article_group_id}", response_model=ArticleGroupWebResponse)
async def update_article_group(
    article_group_id: int,
    body: ArticleGroupUpdateRequest,
    actor: User = Depends(get_current_active_user),
    use_case: UpdateArticleGroup = Depends(get_update_article_group_use_case),
) -> ArticleGroupWebResponse:
    cmd = UpdateArticleGroupCommand(**body.model_dump())
    result = await use_case.execute(actor=actor, article_group_id=article_group_id, cmd=cmd)
    return ArticleGroupWebResponse.model_validate(result.model_dump())


@router.post("/{article_group_id}/archive", response_model=ArticleGroupWebResponse)
async def archive_article_group(
    article_group_id: int,
    actor: User = Depends(get_current_active_user),
    use_case: ArchiveArticleGroup = Depends(get_archive_article_group_use_case),
) -> ArticleGroupWebResponse:
    result = await use_case.execute(actor=actor, article_group_id=article_group_id)
    return ArticleGroupWebResponse.model_validate(result.model_dump())


@router.post("/{article_group_id}/restore", response_model=ArticleGroupWebResponse)
async def restore_article_group(
    article_group_id: int,
    actor: User = Depends(get_current_active_user),
    use_case: RestoreArticleGroup = Depends(get_restore_article_group_use_case),
) -> ArticleGroupWebResponse:
    result = await use_case.execute(actor=actor, article_group_id=article_group_id)
    return ArticleGroupWebResponse.model_validate(result.model_dump())


@router.post("/{article_group_id}/move", status_code=status.HTTP_204_NO_CONTENT)
async def move_article_group(
    article_group_id: int,
    body: ListMoveRequest,
    actor: User = Depends(get_current_active_user),
    use_case: MoveArticleGroup = Depends(get_move_article_group_use_case),
) -> None:
    """Moves the entry one place up or down in the order pickers offer."""
    await use_case.execute(actor, article_group_id, body.direction)


@router.post("/{article_group_id}/place", status_code=status.HTTP_204_NO_CONTENT)
async def place_article_group(
    article_group_id: int,
    body: ListPlaceRequest,
    actor: User = Depends(get_current_active_user),
    use_case: PlaceArticleGroup = Depends(get_place_article_group_use_case),
) -> None:
    """Puts the group next to another one, as dragging its row does."""
    await use_case.execute(
        actor, article_group_id, after_id=body.after_id, before_id=body.before_id
    )
