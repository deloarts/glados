"""
Removes a user's stored time tracking credentials, mounted under the users
path next to users.py: the credentials are Operations' business, while the
user record stays with the user endpoints.
"""

from fastapi import Depends
from fastapi import Response
from fastapi import status
from fastapi.routing import APIRouter

from src.modules.operations.adapters.inbound.api.deps.users import (
    get_delete_user_time_tracking_credentials_use_case,
)
from src.modules.operations.application.use_cases.time_tracking.delete_user_time_tracking_credentials import (
    DeleteUserTimeTrackingCredentials,
)
from src.modules.platform.adapters.inbound.api.auth_deps import get_current_active_user
from src.modules.platform.domain.entities.user import User

router = APIRouter()


@router.delete("/{user_id}/time-tracking-credentials", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user_time_tracking_credentials(
    user_id: int,
    actor: User = Depends(get_current_active_user),
    use_case: DeleteUserTimeTrackingCredentials = Depends(
        get_delete_user_time_tracking_credentials_use_case
    ),
) -> Response:
    """Remove a user's stored time tracking credentials, for example before
    turning the account into a shared or service account, which is refused
    while credentials are stored. Requires write:settings unless it is the
    caller's own account."""
    await use_case.execute(actor=actor, target_id=user_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
