"""
Personal access token (PAT) validation endpoint.
"""

from fastapi import Depends
from fastapi.routing import APIRouter

from src.modules.platform.adapters.inbound.api.auth_deps import get_current_user_pat
from src.modules.platform.adapters.inbound.api.schemas.user_schema import UserResponse
from src.modules.platform.application.dto.user_dto import UserResult
from src.modules.platform.application.mappers.user_mapper import UserMapper
from src.modules.platform.domain.entities.user import User

router = APIRouter()


@router.post("/login/test-personal-access-token", response_model=UserResponse)
async def test_personal_access_token(
    current_user: User = Depends(get_current_user_pat),
) -> UserResult:
    """Validates the PAT and returns the associated user."""
    return UserMapper.to_result(current_user)
