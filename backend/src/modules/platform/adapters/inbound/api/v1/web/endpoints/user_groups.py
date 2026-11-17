"""
User group endpoints, prefix `/user-groups`. Every signed-in user can read
the groups; changes require write:settings.
"""

from fastapi import Depends
from fastapi import status
from fastapi.routing import APIRouter

from src.modules.platform.adapters.inbound.api.auth_deps import get_current_active_user
from src.modules.platform.adapters.inbound.api.deps.users import get_create_user_group_use_case
from src.modules.platform.adapters.inbound.api.deps.users import get_delete_user_group_use_case
from src.modules.platform.adapters.inbound.api.deps.users import get_list_user_groups_use_case
from src.modules.platform.adapters.inbound.api.deps.users import get_update_user_group_use_case
from src.modules.platform.adapters.inbound.api.schemas.user_group_schema import SaveUserGroupRequest
from src.modules.platform.adapters.inbound.api.schemas.user_group_schema import UserGroupResponse
from src.modules.platform.application.dto.user_group_dto import SaveUserGroupCommand
from src.modules.platform.application.dto.user_group_dto import UserGroupResult
from src.modules.platform.application.use_cases.user_group.user_groups import CreateUserGroup
from src.modules.platform.application.use_cases.user_group.user_groups import DeleteUserGroup
from src.modules.platform.application.use_cases.user_group.user_groups import ListUserGroups
from src.modules.platform.application.use_cases.user_group.user_groups import UpdateUserGroup
from src.modules.platform.domain.entities.user import User

router = APIRouter()


@router.get("/", response_model=list[UserGroupResponse])
async def list_user_groups(
    _: User = Depends(get_current_active_user),
    use_case: ListUserGroups = Depends(get_list_user_groups_use_case),
) -> list[UserGroupResult]:
    """Every user group with its permissions and members, by name."""
    return await use_case.execute()


@router.post("/", response_model=UserGroupResponse, status_code=status.HTTP_201_CREATED)
async def create_user_group(
    body: SaveUserGroupRequest,
    actor: User = Depends(get_current_active_user),
    use_case: CreateUserGroup = Depends(get_create_user_group_use_case),
) -> UserGroupResult:
    """Create a group. Requires write:settings."""
    return await use_case.execute(actor=actor, cmd=SaveUserGroupCommand(**body.model_dump()))


@router.put("/{group_id}", response_model=UserGroupResponse)
async def update_user_group(
    group_id: int,
    body: SaveUserGroupRequest,
    actor: User = Depends(get_current_active_user),
    use_case: UpdateUserGroup = Depends(get_update_user_group_use_case),
) -> UserGroupResult:
    """Change a group's name, description, permissions and members. Requires
    write:settings."""
    return await use_case.execute(
        actor=actor, group_id=group_id, cmd=SaveUserGroupCommand(**body.model_dump())
    )


@router.delete("/{group_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user_group(
    group_id: int,
    actor: User = Depends(get_current_active_user),
    use_case: DeleteUserGroup = Depends(get_delete_user_group_use_case),
) -> None:
    """Delete a group; its members lose what only this group granted.
    Requires write:settings."""
    await use_case.execute(actor=actor, group_id=group_id)
