"""
Self-service session management, GitHub-style ("where you're signed in").
Mounted at /api/v1/web/users/me/sessions. Always scoped to the acting
user's own sessions, ending someone else's goes through the admin
force-logout endpoints on /users.
"""

from uuid import UUID

from fastapi import Depends
from fastapi import Response
from fastapi.routing import APIRouter

from src.modules.platform.adapters.inbound.api.auth_deps import get_current_active_user
from src.modules.platform.adapters.inbound.api.deps.auth import get_current_session_use_case
from src.modules.platform.adapters.inbound.api.deps.auth import get_my_sessions_use_case
from src.modules.platform.adapters.inbound.api.deps.auth import (
    get_revoke_my_other_sessions_use_case,
)
from src.modules.platform.adapters.inbound.api.deps.auth import get_revoke_my_session_use_case
from src.modules.platform.adapters.inbound.api.schemas.session_schema import CurrentSessionResult
from src.modules.platform.adapters.inbound.api.schemas.session_schema import RevokedCountResult
from src.modules.platform.adapters.inbound.api.schemas.session_schema import SessionResult
from src.modules.platform.application.use_cases.session.manage_sessions import GetCurrentSession
from src.modules.platform.application.use_cases.session.manage_sessions import GetMySessions
from src.modules.platform.application.use_cases.session.manage_sessions import RevokeMyOtherSessions
from src.modules.platform.application.use_cases.session.manage_sessions import RevokeMySession
from src.modules.platform.domain.entities.user import User
from src.modules.platform.infrastructure.logging.context import current_session_id
from src.modules.platform.infrastructure.security.session_cookie import clear_session_cookie

router = APIRouter()


# Deliberately unpaginated: bounded per-user collection.
@router.get("/", response_model=list[SessionResult])
async def read_my_sessions(
    actor: User = Depends(get_current_active_user),
    use_case: GetMySessions = Depends(get_my_sessions_use_case),
) -> list[SessionResult]:
    """The acting user's live sessions, most recently seen first; the one
    making this request carries is_current."""
    return await use_case.execute(actor, current_session_id())


# Declared ahead of the "/{public_id}" route below (a literal path always
# should be, so an eventual GET "/{public_id}" can never shadow it).
@router.get("/current", response_model=CurrentSessionResult)
async def read_current_session(
    actor: User = Depends(get_current_active_user),
    use_case: GetCurrentSession = Depends(get_current_session_use_case),
) -> CurrentSessionResult:
    """When (if ever) the session making this request hard-expires, plus
    the server's clock, the countdown's entire data source."""
    return await use_case.execute(actor, current_session_id())


@router.delete("/", response_model=RevokedCountResult)
async def revoke_my_other_sessions(
    actor: User = Depends(get_current_active_user),
    use_case: RevokeMyOtherSessions = Depends(get_revoke_my_other_sessions_use_case),
) -> RevokedCountResult:
    """Sign out everywhere else, every session except the current one."""
    count = await use_case.execute(actor, current_session_id())
    return RevokedCountResult(revoked=count)


@router.delete("/{public_id}", response_model=dict)
async def revoke_my_session(
    public_id: UUID,
    response: Response,
    actor: User = Depends(get_current_active_user),
    use_case: RevokeMySession = Depends(get_revoke_my_session_use_case),
) -> dict[str, str]:
    """End one session. Revoking the current one signs this client out, so
    its cookie is cleared too, a revoked row alone would otherwise leave a
    now-useless cookie sitting in the browser until it naturally expires."""
    await use_case.execute(actor, public_id)
    if public_id == current_session_id():
        clear_session_cookie(response)
    return {"detail": "Session revoked"}
