"""
PAT surface, current user lookup.
Lets external scripts and tools (e.g. the SolidWorks addin) discover
which user their PAT belongs to and which permissions it carries.
"""

from fastapi import Depends
from fastapi import Response
from fastapi.routing import APIRouter

from src.modules.platform.adapters.inbound.api.auth_deps import get_current_user_pat
from src.modules.platform.adapters.inbound.api.deps.users import get_user_avatar_use_case
from src.modules.platform.adapters.inbound.api.schemas.user_schema import UserResponse
from src.modules.platform.application.dto.user_dto import UserResult
from src.modules.platform.application.mappers.user_mapper import UserMapper
from src.modules.platform.application.use_cases.user.get_user_avatar import GetUserAvatar
from src.modules.platform.domain.entities.user import User

router = APIRouter()


@router.get("/me", response_model=UserResponse)
async def read_user_me(current_user: User = Depends(get_current_user_pat)) -> UserResult:
    return UserMapper.to_result(current_user)


@router.get("/me/avatar")
async def read_my_avatar(
    current_user: User = Depends(get_current_user_pat),
    use_case: GetUserAvatar = Depends(get_user_avatar_use_case),
) -> Response:
    """Stream the current user's avatar image bytes."""
    data, content_type = await use_case.execute(user_id=current_user.id)
    return Response(
        content=data, media_type=content_type, headers={"Cache-Control": "private, max-age=3600"}
    )
